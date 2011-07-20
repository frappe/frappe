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
	sys.path.append(os.path.join(os.getcwd(), 'cgi-bin'))

def print_cookies():
	if webnotes.cookies or webnotes.add_cookies:
		for c in webnotes.add_cookies.keys():
			webnotes.cookies[c] = webnotes.add_cookies[c]
			print webnotes.cookies


# execution
try:

	set_path()
	
	import webnotes
	import cgi
	form = cgi.FieldStorage()
	#catch22 problem
	requestflds = {}
	for key in form.keys():
		requestflds[key]=form.getvalue(key)
#	raise Exception, webnotes.requestform
	import webnotes.handler
	webnotes.handler.handle(requestflds)
	if(0):
		# Page Call

		# authenticate
		import webnotes.auth
		webnotes.auth.HTTPRequest()
		
		print "Content-Type: text/html"
		print_cookies()

		# print html
		import webnotes.widgets.page_body
		print
		print webnotes.widgets.page_body.get()

except Exception, e:
	d = {'exc':getTraceback().replace('\n','<br>')}
	import json
	print "Content-Type: text/html"
	print
	print json.dumps(d)
