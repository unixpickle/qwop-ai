# QWOP AI

This is an experiment in training an RL agent to play the famous game [QWOP](https://en.wikipedia.org/wiki/QWOP).

I've trained plenty of RL agents before, and I've even [turned HTML5 games into RL environments](https://github.com/unixpickle/muniverse) before. So, instead of focusing on these aspects, this project focuses on infrastructure and scalability. In particular, I am playing with the following ideas/technologies:

 * Redis Pub/Sub
 * Kubernetes Deployments and Services
 * Remote environments running on CPU-only machines.
 * Asynchronous policy stepping.

Here are the components of the training system:

 * Redis - used for communicating between CPU and GPU machines.
 * Master - a GPU machine that takes actions and trains an agent.
 * Workers - a set of CPU instances that asynchronously run multiple environments and ask the master for actions at every timestep.

This setup has a nice consequence: it is really easy to monitor and debug. For example, if every worker sends an environment's frames to a different Redis channel, then a third-party can hook into one of those Redis channels and passively watch the agent play.
