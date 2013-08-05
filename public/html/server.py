#!/usr/bin/env python

# Copyright (c) 2013, Web Notes Technologies Pvt. Ltd.
# MIT License. See license.txt 


from __future__ import unicode_literals
import cgi, cgitb, os, sys
cgitb.enable()

# import libs
sys.path.append('..')
sys.path.append('../lib')
sys.path.append('../app')

import conf

import webnotes
import webnotes.handler
import webnotes.auth


def init():
	webnotes.handler.get_cgi_fields()
	# init request
	try:
		webnotes.http_request = webnotes.auth.HTTPRequest()
		return True
	except webnotes.AuthenticationError, e:
		return True
	#except webnotes.UnknownDomainError, e:
	#	print "Location: " + (conf.redirect_404)
	except webnotes.SessionStopped, e:
		if 'cmd' in webnotes.form_dict:
			webnotes.handler.print_json()
		else:
			print "Content-Type: text/html"
			print
			print """<html>
				<body style="background-color: #EEE;">
					<h3 style="width: 900px; background-color: #FFF; border: 2px solid #AAA; padding: 20px; font-family: Arial; margin: 20px auto">
						Updating.
						We will be back in a few moments...
					</h3>
				</body>
				</html>"""

def respond():
	import webnotes
	if 'cmd' in webnotes.form_dict:
		webnotes.handler.handle()
	else:
		print "Content-Type: text/html"
		print
		print "<html><head><script>window.location.href='index.html';</script></head></html>"

if __name__=="__main__":
	if init():
		respond()
