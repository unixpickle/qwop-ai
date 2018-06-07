"""
Train a QWOP agent.
"""

import argparse
import logging
import os

from anyrl.algos import PPO
from anyrl.models import CNN
from anyrl.spaces import gym_space_distribution, gym_space_vectorizer
import gym
import tensorflow as tf

from qwop_master.conn import Conn
from qwop_master.roller import RemoteRoller


def main():
    args = arg_parser().parse_args()

    if args.verbose:
        logging.basicConfig(level=logging.DEBUG)
    else:
        logging.basicConfig(level=logging.INFO)

    conn = Conn(args.redis_host, args.redis_port, args.channel, obs_size=args.obs_size)

    with tf.Session() as sess:
        model = create_model(args, sess)
        roller = RemoteRoller(model, conn,
                              min_timesteps=args.min_timesteps,
                              min_horizon=args.min_horizon,
                              min_step_batch=args.min_step_batch,
                              timeout=args.env_timeout)
        ppo = PPO(model, epsilon=args.ppo_epsilon, entropy_reg=args.ppo_entropy)
        optimize = ppo.optimize(learning_rate=args.ppo_lr)

        saver = tf.train.Saver()
        ckpt_file = os.path.join(args.checkpoint, 'model.ckpt')

        sess.run(tf.global_variables_initializer())
        if os.path.exists(args.checkpoint):
            saver.restore(sess, ckpt_file)

        while True:
            rollouts = roller.rollouts()
            logging.info('mean cumulative reward: %f',
                         sum(r.total_reward for r in rollouts) / len(rollouts))
            ppo.run_optimize(optimize, rollouts,
                             batch_size=args.ppo_batch,
                             num_iter=args.ppo_iter,
                             log_fn=lambda x: logging.info('%s', x))
            saver.save(sess, os.path.join(args.checkpoint, 'model.ckpt'))


def create_model(args, sess):
    act_space = gym.spaces.MultiBinary(args.act_size)
    obs_space = gym.spaces.Box(low=0, high=0xff, shape=[args.obs_size] * 2 + [3], dtype='uint8')
    return CNN(sess, gym_space_distribution(act_space), gym_space_vectorizer(obs_space))


def arg_parser():
    parser = argparse.ArgumentParser(formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument('--verbose', help='Show debug logs', action='store_true')

    parser.add_argument('--redis-host', help='Redis host', default='qwop-redis')
    parser.add_argument('--redis-port', help='Redis port', default=6379, type=int)
    parser.add_argument('--channel', help='worker channel prefix', default='qwop-worker')
    parser.add_argument('--checkpoint', help='agent checkpoint directory', default='checkpoint')
    parser.add_argument('--obs-size', help='observation image size', default=84, type=int)
    parser.add_argument('--act-size', help='action vector size', default=4, type=int)

    parser.add_argument('--min-timesteps', help='minimum timesteps per batch', default=1024,
                        type=int)
    parser.add_argument('--min-horizon', help='minimum timesteps per rollout', default=16, type=int)
    parser.add_argument('--min-step-batch', help='minimum batch size per step', default=1, type=int)
    parser.add_argument('--env-timeout', help='the environment timeout', default=300, type=int)

    parser.add_argument('--ppo-epsilon', help='the PPO clipping factor', default=0.2, type=float)
    parser.add_argument('--ppo-entropy', help='the PPO entropy bonus', default=0.01, type=float)
    parser.add_argument('--ppo-lr', help='the PPO learning rate', default=1e-4, type=float)
    parser.add_argument('--ppo-batch', help='the PPO batch size', default=256, type=int)
    parser.add_argument('--ppo-iter', help='the PPO iteration count', default=16, type=int)

    return parser


if __name__ == '__main__':
    main()
