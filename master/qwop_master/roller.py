"""
Gathering remote rollouts.
"""

import time

from anyrl.rollouts import Roller, empty_rollout, inject_state, reduce_model_outs, reduce_states


class RemoteRoller(Roller):
    """
    A Roller that gathers rollouts by stepping remote
    environments until there are enough rollouts.
    """

    def __init__(self, model, conn, min_rollouts=64, min_horizon=16, min_step_batch=1, timeout=300):
        """
        Create a new RemoteRoller.

        Args:
          model: the model to run.
          conn: a Conn to a database.
          min_rollouts: the minimum number of rollouts to
            generate per rollouts() call.
          min_horizon: the minimum number of timesteps per
            rollout. Rollouts may be shorter if a done
            condition is met.
          min_step_batch: the minimum number of remote
            environments to step in batch. This can be
            used to force the agent to wait around until
            it can fully utilize the GPU.
          timeout: the time after which an inactive env_id
            is deleted.
        """
        self.model = model
        self.conn = conn
        self.min_rollouts = min_rollouts
        self.min_horizon = min_horizon
        self.min_step_batch = min_step_batch
        self.timeout = timeout

        # A mapping from env_ids to partial Rollouts.
        self._current_rollouts = {}

        # Rollouts that finished due to a done condition.
        self._completed_rollouts = []

    def rollouts(self):
        while not self._has_enough_rollouts():
            state_buffer = self.conn.read_states()
            while len(state_buffer) < self.min_step_batch:
                time.sleep(0.001)
                state_buffer.extend(self.conn.read_states())
            env_ids, obses, rews, news = [], [], [], []
            for state in state_buffer:
                key_names = ['env_id', 'obs', 'rew', 'new']
                for sub_list, key in zip([env_ids, obses, rews, news], key_names):
                    sub_list.append(state[key])
            self._handle_news(env_ids, news)
            self._handle_rewards(env_ids, rews)
            states = self._state_batch(env_ids)
            outputs = self.model.step(obses, states)
            self._handle_step_taken(env_ids, obses, states, outputs)
            self._send_actions(env_ids, outputs['actions'])
            self._remove_timeouts()
        return self._extract_usable_rollouts()

    def _has_enough_rollouts(self):
        """
        Check if we have completed enough rollouts for this
        batch.
        """
        num_rollouts = len(self._completed_rollouts)
        for rollout in self._current_rollouts.values():
            if rollout.num_steps >= self.min_horizon:
                num_rollouts += 1
        return num_rollouts >= len(self.min_rollouts)

    def _extract_usable_rollouts(self):
        """
        Get the usable rollouts and delete them from our
        caches.
        """
        res = self._completed_rollouts
        self._completed_rollouts = []
        for key, rollout in list(self._current_rollouts.items()):
            if rollout.num_steps >= self.min_horizon:
                assert rollout.trunc_end
                res.append(rollout)
                new_rollout = empty_rollout(rollout.step_model_outs[-1]['states'],
                                            prev_steps=rollout.total_steps,
                                            prev_reward=rollout.total_reward)
                new_rollout.observations.append(rollout.observations[-1])
                new_rollout.model_outs.append(rollout.model_outs[-1])
                new_rollout.end_time = time.time()
                self._current_rollouts[key] = new_rollout
        for rollout in res:
            rollout.infos = [{} for _ in range(rollout.num_steps)]
        return res

    def _handle_news(self, env_ids, news):
        """
        Handle episode boundaries.
        """
        for env_id, is_new in zip(env_ids, news):
            if is_new and env_id in self._current_rollouts:
                rollout = self._current_rollouts[env_id]
                # Currently, we do not support final timestep rewards.
                rollout.rewards.append(0)
                rollout.end_time = time.time()
                self._completed_rollouts.append(rollout)
                del self._current_rollouts[env_id]

    def _handle_rewards(self, env_ids, rewards):
        """
        Update our rollouts based on a batch of cumulative
        rewards from a set of environments.
        """
        for env_id, rew in zip(env_ids, rewards):
            if env_id in self._current_rollouts:
                rollout = self._current_rollouts[env_id]
                diff = rew - rollout.total_reward
                rollout.rewards.append(diff)

    def _handle_step_taken(self, env_ids, obses, start_states, outputs):
        """
        Update our rollouts based on an agent's step.
        """
        for i, (env_id, obs) in enumerate(zip(env_ids, obses)):
            reduced = reduce_model_outs(outputs, i)
            if env_id not in self._current_rollouts:
                self._current_rollouts[i] = empty_rollout(reduce_states(start_states, i))
            rollout = self._current_rollouts[i]
            rollout.end_time = time.time()
            rollout.observations.append(obs)
            rollout.model_outs.append(reduced)

    def _send_actions(self, env_ids, actions):
        """
        Send the agent's action choices to the workers.
        """
        self.conn.send_actions(env_ids, actions)

    def _state_batch(self, env_ids):
        """
        Get the current model state for each env_id.
        """
        state_batch = self.model.start_state(len(env_ids))
        for i, env_id in enumerate(env_ids):
            if env_id in self._current_rollouts:
                rollout = self._current_rollouts[env_id]
                if len(rollout.step_model_outs):
                    inject_state(state_batch, rollout.step_model_outs[-1]['states'], i)
                else:
                    inject_state(state_batch, rollout.start_state, i)
        return state_batch

    def _remove_timeouts(self):
        """
        Remove rollouts that have timed out.
        """
        for key, rollout in list(self._current_rollouts.items()):
            if rollout.end_time + self.timeout < time.time():
                del self._current_rollouts[key]
