#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""The setup script."""

import sys
from setuptools import setup, find_packages


if sys.version_info < (3, 5):
    print('sockio needs python >= 3.5')
    exit(1)

TESTING = any(x in sys.argv for x in ["test", "pytest"])

setup_requirements = []
if TESTING:
    setup_requirements += ['pytest-runner']
test_requirements = ['pytest', 'pytest-cov', 'pytest-asyncio']


description = '''\
sockio
======

A concurrency agnostic socket library on python.

So far implemented REQ-REP semantics with auto-reconnection facilites.

Implementations for:

* classic blocking API
* future based API
* asyncio

Join the party by bringing your own concurrency library with a PR!

I am looking in particular for implementations over trio and curio.

Installation
------------

From within your favourite python environment::

    pip install sockio


Usage
-----

asyncio
#######

::

    import asyncio
    from sockio.aio import Socket

    async def main():
        sock = Socket('acme.example.com', 5000)
        # Assuming a SCPI complient on the other end we can ask for:
        reply = await sock.write_readline(b'*IDN?\n')
        print(reply)

    asyncio.run(main())


classic
#######

::

    from sockio.sio import Socket

    sock = Socket('acme.example.com', 5000)
    # Assuming a SCPI complient on the other end we can ask for:
    reply = sock.write_readline(b'*IDN?\n')
    print(reply)

'''

setup(
    name='sockio',
    author="Jose Tiago Macara Coutinho",
    author_email='coutinhotiago@gmail.com',
    classifiers=[
        'Development Status :: 2 - Pre-Alpha',
        'Intended Audience :: Developers',
        'Natural Language :: English',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.5',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: 3.7'
    ],
    description="Concurrency agnostic socket API",
    license="MIT license",
    long_description=description,
    keywords='socket, asyncio',
    packages=find_packages(include=['sockio']),
    setup_requires=setup_requirements,
    test_suite='tests',
    tests_require=test_requirements,
    url='https://github.com/tiagocoutinho/sockio',
    version='0.1.2',
    zip_safe=True
)
