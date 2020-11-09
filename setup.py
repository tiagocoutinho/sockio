# -*- coding: utf-8 -*-

"""The setup script."""

import sys
from setuptools import setup, find_packages

with open("README.md") as f:
    description = f.read()

setup(
    name="sockio",
    author="Jose Tiago Macara Coutinho",
    author_email="coutinhotiago@gmail.com",
    classifiers=[
        "Development Status :: 2 - Pre-Alpha",
        "Intended Audience :: Developers",
        "Natural Language :: English",
        "Programming Language :: Python :: 2.7",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.5",
        "Programming Language :: Python :: 3.6",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
    ],
    description="Concurrency agnostic socket API",
    license="GPLv3+",
    long_description=description,
    long_description_content_type="text/markdown",
    keywords="socket, asyncio",
    packages=find_packages(include=["sockio"]),
    url="https://tiagocoutinho.github.io/sockio/",
    project_urls={
        "Documentation": "https://tiagocoutinho.github.io/sockio/",
        "Source": "https://github.com/tiagocoutinho/sockio/",
    },
    version="0.14.0",
    python_requires=">=2.7",
    zip_safe=True,
)
