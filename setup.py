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
    if sys.version_info < (3, 7):
        print('testing sockio needs python >= 3.7')
        exit(1)
    setup_requirements += ['pytest-runner']
test_requirements = ['pytest', 'pytest-cov', 'pytest-asyncio']

with open('README.md') as f:
    description = f.read()

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
    license="GPLv3+",
    long_description=description,
    long_description_content_type='text/markdown',
    keywords='socket, asyncio',
    packages=find_packages(include=['sockio']),
    setup_requires=setup_requirements,
    test_suite='tests',
    tests_require=test_requirements,
    url='https://tiagocoutinho.github.io/sockio/',
    version='0.3.1',
    python_requires='>=3.5',
    zip_safe=True
)
