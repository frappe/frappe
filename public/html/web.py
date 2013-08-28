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

session_stopped = """<!DOCTYPE html>
<html lang="en">
<head>
	<title>Session Stopped</title>
</head>
<body style="background-color: #eee; font-family: Arial, Sans Serif;">
<div style="margin: 30px auto; width: 500px; background-color: #fff; 
	border: 1px solid #aaa; padding: 20px; text-align: center">
	<b>%(app_name)s: Upgrading...</b>
	<p>We will be back in a few moments.</p>
</div>
</body>
</html>"""

def init():
	import webnotes.handler
	webnotes.handler.get_cgi_fields()

def respond():
	import webnotes
	import webnotes.webutils
	import MySQLdb
	
	try:
		return webnotes.webutils.render(webnotes.form_dict.get('page'))
	except webnotes.SessionStopped:
		print "Content-type: text/html"
		print
		print session_stopped
	except MySQLdb.ProgrammingError, e:
		if e.args[0]==1146:
			print "Content-type: text/html"
			print
			print session_stopped % {"app_name": webnotes.get_config().app_name}
		else:
			raise e

if __name__=="__main__":
	init()
	respond()