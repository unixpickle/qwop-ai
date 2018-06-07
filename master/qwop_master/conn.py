"""
Communicating with remote workers.
"""

import logging
from threading import Lock, Thread

import numpy as np
import redis


class Conn:
    """
    A connection that can read observations from and send
    actions to workers.
    """

    def __init__(self, redis_host, redis_port, channel_prefix, obs_size=84):
        self._channel_prefix = channel_prefix
        self._obs_size = obs_size
        self._conn = redis.StrictRedis(host=redis_host, port=redis_port)
        self._bg_thread = Thread(target=self._run_read_loop, daemon=True)
        self._bg_thread.start()
        self._pending_lock = Lock()
        self._pending_messages = []

    def read_states(self):
        """
        Get the current buffer of messages, emptying the
        buffer in the process.

        Returns:
          A list of dicts with the following keys:
            env_id: an ID for the environment.
            obs: the numpy array observation.
            rew: the reward.
            new: whether or not this is the first timestep
              of a new episode.
        """
        with self._pending_lock:
            res = self._pending_messages
            self._pending_messages = []
            return res

    def send_actions(self, env_ids, actions):
        """
        Send actions back to a set of environments.

        Args:
          env_ids: a list of environment IDs.
          actions: a list of action arrays, where each
            action is an array-like of four booleans.
        """
        with self._conn.pipeline() as pipe:
            for env_id, action in zip(env_ids, actions):
                logging.debug('sending action %r to env %s', action, env_id)
                act_str = ''.join('1' if x else '0' for x in action)
                pipe.publish('%s:act:%s' % (self._channel_prefix, env_id), act_str)

    def _run_read_loop(self):
        pubsub = self._conn.pubsub()
        pubsub.psubscribe('%s:state:*' % self._channel_prefix)
        while True:
            msg = pubsub.get_message()
            if msg['type'] != 'message':
                continue
            data = msg['data']
            obs_buf_size = 3 * (self._obs_size ** 2)
            if len(data) < obs_buf_size + 2:
                logging.warning('state message is too small (%d bytes)', len(data))
                continue
            env_id = msg['channel'].split(':')[-1]
            obs = np.frombuffer(data[:obs_buf_size],
                                dtype='uint8',
                                shape=(self._obs_size, self._obs_size, 3))
            done = (data[obs_buf_size] != 0)
            rew = float(str(data[obs_buf_size + 1:], 'utf-8'))
            logging.debug('message from %s: rew=%f done=%r', env_id, rew, done)
            with self._pending_lock:
                self._pending_messages.append({
                    'env_id': env_id,
                    'obs': obs,
                    'rew': rew,
                    'new': done,
                })
