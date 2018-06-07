"""
Monitor activity of all the environments.
"""

import argparse

import redis


def main():
    args = arg_parser().parse_args()

    conn = redis.StrictRedis(host=args.redis_host, port=args.redis_port)
    pubsub = conn.pubsub()
    pubsub.psubscribe(args.channel + ':state:*')
    for msg in pubsub.listen():
        if msg['type'] != 'pmessage':
            continue
        env_id = str(msg['channel'], 'utf-8').split(':')[-1]
        print('state from env_id: %s' % env_id)


def arg_parser():
    parser = argparse.ArgumentParser(formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument('--redis-host', help='Redis host', default='qwop-redis')
    parser.add_argument('--redis-port', help='Redis port', default=6379, type=int)
    parser.add_argument('--channel', help='channel prefix', default='qwop-worker')
    return parser


if __name__ == '__main__':
    main()
