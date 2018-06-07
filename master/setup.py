"""
A setuptools-based setup module.
"""

from setuptools import setup

setup(
    name='qwop-master',
    version='0.0.1',
    description='Learn a QWOP agent.',
    url='https://github.com/unixpickle/qwop-ai',
    author='Alex Nichol',
    author_email='unixpickle@gmail.com',
    packages=['qwop_master'],
    install_requires=[
        'numpy>=1.0.0,<2.0.0',
        'anyrl>=0.11.29,<0.12.0',
        'tensorflow-gpu'
    ]
)
