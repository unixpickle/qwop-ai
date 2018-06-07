"""
Communicating with remote workers.
"""

import logging
from threading import Lock, Thread

import numpy as np
import redis

LOGGER = logging.getLogger('conn')


class Conn:
    """
    A connection that can read observations from and send
    actions to workers.
    """

    def __init__(self, redis_host, redis_port, channel_prefix, obs_size=84):
        self._channel_prefix = channel_prefix
        self._obs_size = obs_size
        self._conn = redis.StrictRedis(host=redis_host, port=redis_port)
        self._conn.ping()
        self._bg_thread = Thread(target=self._run_read_loop, daemon=True)
        self._bg_thread.start()
        self._pending_lock = Lock()
        self._pending_messages = []
        self._pending_error = None

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
            if self._pending_error is not None:
                raise self._pending_error  # pylint: disable=E0702
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
        for env_id, action in zip(env_ids, actions):
            channel = '%s:act:%s' % (self._channel_prefix, env_id)
            act_str = ''.join('1' if x else '0' for x in action)
            LOGGER.debug('sending action %s to env %s (channel %s)', act_str, env_id, channel)
            self._conn.publish(channel, act_str)

    def _run_read_loop(self):
        try:
            pubsub = self._conn.pubsub()
            pubsub.psubscribe('%s:state:*' % self._channel_prefix)
            for msg in pubsub.listen():
                self._handle_message(msg)
        except redis.exceptions.RedisError as exc:
            with self._pending_lock:
                self._pending_error = exc

    def _handle_message(self, msg):
        LOGGER.debug('got message of type %s on channel %s', msg['type'], msg['channel'])
        if msg['type'] != 'pmessage':
            return
        data = msg['data']
        obs_buf_size = 3 * (self._obs_size ** 2)
        if len(data) < obs_buf_size + 2:
            LOGGER.warning('state message is too small (%d bytes)', len(data))
            return
        env_id = str(msg['channel'], 'utf-8').split(':')[-1]
        obs = np.frombuffer(data[:obs_buf_size], dtype='uint8')
        obs = obs.reshape((self._obs_size, self._obs_size, 3))
        done = (data[obs_buf_size] != 0)
        rew = float(str(data[obs_buf_size + 1:], 'utf-8'))
        LOGGER.debug('message from %s: rew=%f done=%r', env_id, rew, done)
        with self._pending_lock:
            self._pending_messages.append({
                'env_id': env_id,
                'obs': obs,
                'rew': rew,
                'new': done,
            })
