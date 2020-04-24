#!/usr/bin/env python

from setuptools import setup, find_packages

setup(
    name='file_manager',
    version='0.0.1',
    description='This package consists of reusable code to read and write different types of files.',
    author='Deepak',
    author_email='deepak.nair@dataweave.com',
    packages=find_packages(exclude=["*.tests", "*.tests.*", "tests.*", "tests"]),
    license='LICENSE.txt',
)