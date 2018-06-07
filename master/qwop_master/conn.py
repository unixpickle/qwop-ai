"""
Communicating with remote workers.
"""

import logger
from threading import Lock

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
        # TODO: this.

    def _run_read_loop(self):
        pubsub = self._conn.pubsub()
        pubsub.psubscribe('%s:state:*' % self._channel_prefix)
        while True:
            msg = pubsub.get_message()
            if msg['type'] != 'message':
                continue
            if len(msg['data']) < 3 * (self._obs_size ** 2) + 2:
                logger.warning('state message is too small (%d bytes)' % len(msg['data']))
                continue
            env_id = msg['channel'].split(':')[-1]
            # TODO: decode image, done, and reward.
            with self._pending_lock:
                # TODO: push to self._pending_messages
                pass
