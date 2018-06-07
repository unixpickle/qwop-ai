"""
Train a QWOP agent.
"""

import argparse


def main():
    args = arg_parser().parse_args()
    # TODO: this.


def arg_parser():
    parser = argparse.ArgumentParser(formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument('--redis', help='Redis host', default='qwop-redis:6379')
    parser.add_argument('--channel', help='Worker channel prefix', default='qwop-worker')
    return parser


if __name__ == '__main__':
    main()
