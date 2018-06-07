"""
Communicating with remote workers.
"""

from threading import Lock


class Conn:
    """
    A connection that can read observations from and send
    actions to workers.
    """

    def __init__(self, redis_addr):
        # TODO: connect here.
        self._conn = None
        # TODO: start background thread here.
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
