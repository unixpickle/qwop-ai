"""
Monitor activity of all the environments.
"""

import argparse
import time

import redis


def main():
    args = arg_parser().parse_args()

    conn = redis.StrictRedis(host=args.redis_host, port=args.redis_port)
    pubsub = conn.pubsub()
    pubsub.psubscribe(args.channel + ':state:*')
    env_list = []
    sizes = []
    last_time = time.time()
    for msg in pubsub.listen():
        if msg['type'] != 'pmessage':
            continue
        env_id = str(msg['channel'], 'utf-8').split(':')[-1]
        env_list.append(env_id)
        sizes.append(len(msg['data']))
        elapsed = time.time() - last_time
        if elapsed >= args.interval:
            print('---')
            print('env_ids: %r' % set(env_list))
            print('tps: %f' % (len(env_list) / elapsed))
            print('bytes/sec: %f' % (sum(sizes) / elapsed))
            env_list = []
            sizes = []
            last_time = time.time()


def arg_parser():
    parser = argparse.ArgumentParser(formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument('--redis-host', help='Redis host', default='qwop-redis')
    parser.add_argument('--redis-port', help='Redis port', default=6379, type=int)
    parser.add_argument('--channel', help='channel prefix', default='qwop-worker')
    parser.add_argument('--interval', help='log interval', default=2, type=float)
    return parser


if __name__ == '__main__':
    main()
