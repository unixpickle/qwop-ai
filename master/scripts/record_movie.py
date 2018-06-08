"""
Dump a Redis stream of PNG images.
"""

import argparse
import os

import redis


def main():
    args = arg_parser().parse_args()
    for i, image in enumerate(read_frames(args)):
        if i == 0:
            os.mkdir(args.out_dir)
        path = os.path.join(args.out_dir, '%06d.png' % i)
        with open(path, 'wb+') as out_file:
            out_file.write(image)


def read_frames(args):
    conn = redis.StrictRedis(host=args.redis_host, port=args.redis_port)
    pubsub = conn.pubsub()
    pubsub.subscribe(args.channel)
    for msg in pubsub.listen():
        if msg['type'] != 'message':
            continue
        yield msg['data']


def arg_parser():
    parser = argparse.ArgumentParser(formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument('--redis-host', help='Redis host', default='qwop-redis')
    parser.add_argument('--redis-port', help='Redis port', default=6379, type=int)
    parser.add_argument('--out-dir', help='output directory', default='output')
    parser.add_argument('channel', help='channel prefix')
    return parser


if __name__ == '__main__':
    main()
