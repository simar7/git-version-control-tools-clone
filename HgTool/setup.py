#!/usr/bin/python

from distutils.core import setup

setup(
    name='hgtool',
    version='1.0.0',
    author='Chris AtLee',
    author_email='catlee@mozilla.com',
    packages=['hgtool'],
    # XXX: Update URL when submitted.
    url='',
    license='LICENSE',
    descripton='hgtool allows to do safe operations with hg',
    long_description=open('README.txt').read(),
)
