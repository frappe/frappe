#!/usr/bin/env python

# Copyright (c) 2013, Web Notes Technologies Pvt. Ltd.
# MIT License. See license.txt

"""
	return a dynamic page from website templates

	all html pages related to website are generated here
"""
from __future__ import unicode_literals
import cgi, cgitb, os, sys
cgitb.enable()

# import libs

sys.path.append('..')
sys.path.append('../lib')
sys.path.append('../app')

import conf

def init():
	import webnotes.handler
	webnotes.handler.get_cgi_fields()

def respond():
	import webnotes
	import webnotes.webutils
	return webnotes.webutils.render(webnotes.form_dict.get('page'))

if __name__=="__main__":
	init()
	respond()