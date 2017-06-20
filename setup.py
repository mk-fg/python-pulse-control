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
	version = '17.6.0',
	author = 'George Filipkin, Mike Kazantsev',
	author_email = 'mk.fraggod@gmail.com',
	license = 'MIT',
	keywords = [
		'pulseaudio', 'libpulse', 'pulse', 'pa', 'bindings',
		'sound', 'audio',
		'ctypes', 'control', 'mixer', 'volume', 'mute', 'source', 'sink' ],

	url = 'http://github.com/mk-fg/python-pulse-control',

	description = 'Python high-level interface'
		' and ctypes-based bindings for PulseAudio (libpulse)',
	long_description = readme,

	classifiers = [
		'Development Status :: 4 - Beta',
		'Intended Audience :: Developers',
		'License :: OSI Approved :: MIT License',
		'Operating System :: POSIX',
		'Operating System :: POSIX :: Linux',
		'Programming Language :: Python',
		'Programming Language :: Python :: 2',
		'Programming Language :: Python :: 2.7',
		'Programming Language :: Python :: 3',
		'Programming Language :: Python :: 3.5',
		'Topic :: Multimedia',
		'Topic :: Multimedia :: Sound/Audio' ],

	install_requires = ['setuptools'],

	packages = find_packages(),
	include_package_data = True )
