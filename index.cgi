#!/usr/bin/python

# Chai Project 0.1
# (c) 2011 Web Notes Technologies
# Chai Project may be freely distributed under MIT license
# Authors: Rushabh Mehta (rmehta at gmail)

"""
	Entry point for all server requests
	If "cmd" is a form (url) variable, then it passes over control to `handler.py`
	If there no "cmd", it returns the HTML for a full page load
"""

def getTraceback():
	"""
		Returns traceback
	"""
	import sys, traceback, string
		type, value, tb = sys.exc_info()
		body = "Traceback (innermost last):\n"
		list = traceback.format_tb(tb, None) + traceback.format_exception_only(type, value)
		body = body + "%-20s %s" % (string.join(list[:-1], ""), list[-1])
		return body
		
def set_path():
	"""
		Set path to "webnotes" module. This can be skipped if PYTHONPATH is set
		We don't use PYTHONPATH because we may want to run multiple versions of
		the framework on the same server
	"""
	import sys, os
	sys.path.append(os.path.join(os.getcwd(), '..', 'server'))

# execution
try:

	set_path()
	
	from chai.handler import handle

	if webnotes.form.getvalue('cmd'):
		# Function handled by handler
		import webnotes.handler
	else:
		# Page Call

		# authenticate
		import webnotes.auth
		webnotes.auth.HTTPRequest()

		print_header()

		# print html
		import webnotes.widgets.page_body
		print webnotes.widgets.page_body.get_html()

except Exception, e:
	print "Content-Type: text/html"
	print
	print getTraceback().replace('\n','<br>')
   	print e	
