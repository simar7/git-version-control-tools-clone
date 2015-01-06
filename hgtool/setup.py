#!/usr/bin/env/ python

from distutils.core import setup
from setuptools import find_packages

setup(
    name='hgtool',
    version='1.0.0',
    author='Chris AtLee',
    author_email='catlee@mozilla.com',
    packages=find_packages(),
    # XXX: Update URL when submitted.
    url='',
    license='LICENSE',
    description='hgtool allows to do safe operations with hg',
    long_description=open('README.txt').read(),
    entry_points = {
        'console_scripts': [
            'hgtool = hgtool.hgtool:main',
            ],
        }
)
