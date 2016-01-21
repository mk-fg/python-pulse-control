#!/usr/bin/env python2
#-*- coding: utf-8 -*-

from setuptools import setup, find_packages
import os, sys

# Error-handling here is to allow package to be built w/o README included
try:
	readme = open(os.path.join(
		os.path.dirname(__file__), 'README.rst' )).read()
except IOError: readme = ''

setup(

	name = 'pulsectl',
	version = '16.1.16',
	author = 'George Filipkin, Mike Kazantsev',
	author_email = 'mk.fraggod@gmail.com',
	license = 'MIT',
	keywords = [
		'pulseaudio', 'libpulse', 'pulse', 'pa', 'bindings',
		'sound', 'audio',
		'ctypes', 'control', 'mixer', 'volume', 'mute', 'source', 'sink' ],

	url = 'http://github.com/mk-fg/python-pulse-control',

	description = 'Python ctypes bindings for pulseaudio (libpulse).',
	long_description = readme,

	classifiers = [
		'Development Status :: 4 - Beta',
		'Intended Audience :: Developers',
		'License :: OSI Approved :: MIT License',
		'Operating System :: POSIX',
		'Operating System :: POSIX :: Linux',
		'Programming Language :: Python',
		'Programming Language :: Python :: 2.7',
		'Programming Language :: Python :: 2 :: Only',
		'Topic :: Multimedia',
		'Topic :: Multimedia :: Sound/Audio' ],

	install_requires = ['setuptools'],

	packages = find_packages(),
	include_package_data = True )
