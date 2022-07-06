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
    install_requires=[
        "boto3",
        "Deprecated",
        "fastparquet==0.3.3",
        "lxml==4.9.1",
        "openpyxl==3.0.3",
        "pandas==1.0.3",
        "pyarrow==0.17.0",
        "s3fs==0.4.2",
        "xmltodict==0.12.0",
        "numpy==1.18.3"
    ],
)