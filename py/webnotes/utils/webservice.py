# Copyright (c) 2012 Web Notes Technologies Pvt Ltd (http://erpnext.com)
# 
# MIT License (MIT)
# 
# Permission is hereby granted, free of charge, to any person obtaining a 
# copy of this software and associated documentation files (the "Software"), 
# to deal in the Software without restriction, including without limitation 
# the rights to use, copy, modify, merge, publish, distribute, sublicense, 
# and/or sell copies of the Software, and to permit persons to whom the 
# Software is furnished to do so, subject to the following conditions:
# 
# The above copyright notice and this permission notice shall be included in 
# all copies or substantial portions of the Software.
# 
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, 
# INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A 
# PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT 
# HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF 
# CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE 
# OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
# 

from __future__ import unicode_literals
import webnotes
import webnotes.utils

class FrameworkServer:
	"""
	   Connect to a remote server via HTTP (webservice).
	   
	   * `remote_host` is the the address of the remote server
	   * `path` is the path of the Framework (excluding index.cgi)
	"""
	def __init__(self, remote_host, path, user='', password='', account='', cookies=None, opts=None, https = 0):
		# validate
		if not (remote_host and path):
			raise Exception, "Server address and path necessary"

		if not ((user and password) or (cookies)):
			raise Exception, "Either cookies or user/password necessary"
	
		self.remote_host = remote_host
		self.path = path
		self.cookies = cookies or {}
		self.webservice_method='POST'
		self.account = account
		self.account_id = None
		self.https = https
		self.conn = None

		# login
		if not cookies:
			args = { 'usr': user, 'pwd': password, 'ac_name': account }
			
			if opts:
				args.update(opts)
			
			res = self.http_get_response('login', args)
		
			ret = res.read()
			try:
				ret = eval(ret)
			except Exception, e:
				webnotes.msgprint(ret)
				raise Exception, e
				
			if 'message' in ret and ret['message']!='Logged In':
				webnotes.msgprint(ret.get('server_messages'), raise_exception=1)
				
			if ret.get('exc'):
				raise Exception, ret.get('exc')
				
			self._extract_cookies(res)

			self.account_id = self.cookies.get('account_id')
			self.sid = self.cookies.get('sid')
			
			self.login_response = res
			self.login_return = ret

	# -----------------------------------------------------------------------------------------

	def http_get_response(self, method, args):
		"""
		Run a method on the remote server, with the given arguments
		"""
		# get response from remote server
	
		import urllib, urllib2, os

		args['cmd'] = method
		if self.path.startswith('/'): self.path = self.path[1:]
				
		protocol = self.https and 'https://' or 'http://'
		req = urllib2.Request(protocol + os.path.join(self.remote_host, self.path, 'index.cgi'), \
			urllib.urlencode(args))
		for key in self.cookies:
			req.add_header('cookie', '; '.join(['%s=%s' % (key, self.cookies[key]) \
				for key in self.cookies]))

		return urllib2.urlopen(req)

	# -----------------------------------------------------------------------------------------
	
	def _extract_cookies(self, res):
		import Cookie
		cookies = Cookie.SimpleCookie()
		cookies.load(res.headers.get('set-cookie'))
		for c in cookies.values():
			self.cookies[c.key] = c.value.rstrip(',')

	# -----------------------------------------------------------------------------------------


	def runserverobj(self, doctype, docname, method, arg=''):
		"""
		Returns the response of a remote method called on a system object specified by `doctype` and `docname`
		"""
		import json
		res = self.http_get_response('runserverobj', args = {
			'doctype':doctype
			,'docname':docname
			,'method':method
			,'arg':arg
		})
		ret = json.loads(res.read())
		if ret.get('exc'):
			raise Exception, ret.get('exc')
		return ret
	
	# -----------------------------------------------------------------------------------------
			
	def run_method(self, method, args={}):
		"""
			Run a method on the remote server
		"""
		res = self.http_get_response(method, args).read()
		import json
		try:
			ret = json.loads(res)
		except Exception, e:
			webnotes.msgprint('Bad Response: ' + res, raise_exception=1)
		if ret.get('exc'):
			raise Exception, ret.get('exc')
		return ret
