#!/usr/bin/env python3

from distutils.core import setup

setup(
	name='qanda',
	version='0.0.1',
	author='Zane van Iperen',
	author_email='zane@zanevaniperen.com',
	requires=['beautifulsoup4', 'html5lib', 'feedgen'],
	packages=['qanda'],
	scripts=['bin/qanda']
)
