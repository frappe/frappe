#!/usr/bin/python
# -*- coding: utf-8 -*-

# Script for creating the pypi packages
# Works only for python 2.6+


import os

try:
    from setuptools import setup, find_packages
except ImportError:
    import ez_setup
    ez_setup.use_setuptools()
    from setuptools import setup, find_packages

# Startup
appname = "webnotes-core"
appversion = "v170"

setup(
        name = appname,
        version = appversion,
        author = "Rushabh Mehta",
        namespace_packages = ["webnotes"],
        packages = ["webnotes"] + [ os.path.join("webnotes", a) for a in find_packages("webnotes") ],
        author_email = "rmehta@gmail.com",
        description = "A meta-data based library for creating web apps in python and javascript",
        license = "MIT",
        keywords = "Meta-data web app framework python",
        url = "http://code.google.com/p/webnotes/",
        classifiers = ["License :: OSI Approved :: MIT License","Topic :: Software Development :: Libraries :: Python Modules"],
        long_description = "Webnotes is a meta-data based framework for web applications in python",
)

