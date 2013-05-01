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
import sys, os
import webnotes
import webnotes.utils
import webnotes.sessions

form = webnotes.form
form_dict = webnotes.form_dict

sql = None
session = None
errdoc = ''
errdoctype = ''
errmethod = ''

def get_cgi_fields():
	"""make webnotes.form_dict from cgi field storage"""
	import cgi
	import webnotes
	from webnotes.utils import cstr
	
	# make the form_dict
	webnotes.form = cgi.FieldStorage(keep_blank_values=True)
	for key in webnotes.form.keys():
		# file upload must not be decoded as it is treated as a binary
		# file and hence in any encoding (it does not matter)
		if not getattr(webnotes.form[key], 'filename', None):
			webnotes.form_dict[key] = cstr(webnotes.form.getvalue(key))

@webnotes.whitelist(allow_guest=True)
def startup():
	webnotes.response.update(webnotes.sessions.get())

def cleanup_docs():
	import webnotes.model.utils
	if webnotes.response.get('docs') and type(webnotes.response['docs'])!=dict:
		webnotes.response['docs'] = webnotes.model.utils.compress(webnotes.response['docs'])

@webnotes.whitelist()
def runserverobj(arg=None):
	import webnotes.widgets.form.run_method
	webnotes.widgets.form.run_method.runserverobj()

@webnotes.whitelist(allow_guest=True)
def logout():
	webnotes.login_manager.logout()

@webnotes.whitelist(allow_guest=True)
def web_logout():
	webnotes.repsond_as_web_page("Logged Out", """<p>You have been logged out.</p>
		<p><a href='index'>Back to Home</a></p>""")
	webnotes.login_manager.logout()


@webnotes.whitelist()
def dt_map():
	import webnotes
	import webnotes.model.utils
	from webnotes.model.code import get_obj
	from webnotes.model.doc import Document
	from webnotes.model.bean import Bean
	
	form_dict = webnotes.form_dict
	
	dt_list = webnotes.model.utils.expand(form_dict.get('docs'))
	from_doctype = form_dict.get('from_doctype')
	to_doctype = form_dict.get('to_doctype')
	from_docname = form_dict.get('from_docname')
	from_to_list = form_dict.get('from_to_list')
	
	dm = get_obj('DocType Mapper', from_doctype +'-' + to_doctype)
	dl = dm.dt_map(from_doctype, to_doctype, from_docname, Document(fielddata = dt_list[0]), (len(dt_list) > 1) and Bean(dt_list).doclist or [], from_to_list)
	
	webnotes.response['docs'] = dl

@webnotes.whitelist()
def uploadfile():
	import webnotes.utils
	import webnotes.utils.file_manager
	import json

	try:
		if webnotes.form_dict.get('from_form'):
			try:
				ret = webnotes.utils.file_manager.upload()
			except webnotes.DuplicateEntryError, e:
				# ignore pass
				ret = None
				webnotes.conn.rollback()
		else:
			if webnotes.form_dict.get('method'):
				ret = webnotes.get_method(webnotes.form_dict.method)()
	except Exception, e:
		webnotes.errprint(webnotes.utils.getTraceback())
		ret = None

	return ret
	
@webnotes.whitelist(allow_guest=True)
def reset_password(user):
	from webnotes.model.code import get_obj
	from webnotes.utils import random_string
	
	user = webnotes.form_dict.get('user', '')
	if user in ["demo@erpnext.com", "Administrator"]:
		return "Not allowed"
		
	if webnotes.conn.sql("""select name from tabProfile where name=%s""", user):
		new_password = random_string(8)
		webnotes.conn.sql("""update `__Auth` set password=password(%s)
			where `user`=%s""", (new_password, user))

		# Hack!
		webnotes.session["user"] = "Administrator"
		profile = get_obj("Profile", user)
		profile.password_reset_mail(new_password)
		return "Password has been reset and sent to your email id."
	else:
		return "No such user (%s)" % user


def handle():
	"""handle request"""
	cmd = webnotes.form_dict['cmd']

	if cmd!='login':
		# login executed in webnotes.auth
		if webnotes.request_method == "POST":
			webnotes.conn.begin()
		
		try:
			execute_cmd(cmd)
		except webnotes.ValidationError, e:
			webnotes.errprint(e)
			if webnotes.request_method == "POST":
				webnotes.conn.rollback()
		except:
			webnotes.errprint(webnotes.utils.getTraceback())
			if webnotes.request_method == "POST":
				webnotes.conn and webnotes.conn.rollback()

		if webnotes.request_method == "POST" and webnotes.conn:
			webnotes.conn.commit()
				
	print_response()

	if webnotes.conn:
		webnotes.conn.close()
	if webnotes._memc:
		webnotes._memc.disconnect_all()

def execute_cmd(cmd):
	"""execute a request as python module"""
	method = get_method(cmd)

	# check if whitelisted
	if webnotes.session['user'] == 'Guest':
		if (method not in webnotes.guest_methods):
			webnotes.response['403'] = 1
			raise Exception, 'Not Allowed, %s' % str(method)
	else:
		if not method in webnotes.whitelisted:
			webnotes.response['403'] = 1
			webnotes.msgprint('Not Allowed, %s' % str(method))
			raise Exception, 'Not Allowed, %s' % str(method)
		
	ret = call(method, webnotes.form_dict)

	# returns with a message
	if ret:
		webnotes.response['message'] = ret

	# update session
	webnotes.session_obj.update()


def call(fn, args):
	import inspect
	fnargs, varargs, varkw, defaults = inspect.getargspec(fn)
	newargs = {}
	for a in fnargs:
		if a in args:
			newargs[a] = args.get(a)
	return fn(**newargs)

def get_method(cmd):
	"""get method object from cmd"""
	if '.' in cmd:
		method = webnotes.get_method(cmd)
	else:
		method = globals()[cmd]
	webnotes.log("method:" + cmd)
	return method
			
def print_response():
	print_map = {
		'csv': print_csv,
		'iframe': print_iframe,
		'download': print_raw,
		'json': print_json,
		'page': print_page
	}
	
	print_map.get(webnotes.response.get('type'), print_json)()

def print_page():
	"""print web page"""
	print_cookie_header()

	from webnotes.webutils import render
	render(webnotes.response['page_name'])

def eprint(content):
	print content.encode('utf-8')

def print_json():	
	make_logs()
	cleanup_docs()
	print_cookie_header()

	eprint("Content-Type: text/html; charset: utf-8")

	import json
	print_zip(json.dumps(webnotes.response, default=json_handler, separators=(',',':')))
		
def print_csv():
	eprint("Content-Type: text/csv; charset: utf-8")
	eprint("Content-Disposition: attachment; filename=%s.csv" % webnotes.response['doctype'].replace(' ', '_'))
	eprint("")
	eprint(webnotes.response['result'])

def print_iframe():
	eprint("Content-Type: text/html; charset: utf-8")
	eprint("")
	eprint(webnotes.response.get('result') or '')
	
	if webnotes.error_log:
		import json
		eprint("""\
			<script>
				var messages = %(messages)s;
				if (messages.length) {
					for (var i in messages) {
						window.parent.msgprint(messages[i]);
					}
				}
				var errors = %(errors)s;
				if (errors.length) {
					for (var i in errors) {
						window.parent.console.log(errors[i]);
					}
				}
			</script>""" % {
				'messages': json.dumps(webnotes.message_log).replace("'", "\\'"),
				'errors': json.dumps(webnotes.error_log).replace("'", "\\'"),
			})

def print_raw():
	eprint("Content-Type: %s" % \
		mimetypes.guess_type(webnotes.response['filename'])[0] \
		or 'application/unknown'),
	eprint("Content-Disposition: filename=%s" % \
		webnotes.response['filename'].replace(' ', '_'))
	eprint("")
	eprint(webnotes.response['filecontent'])

def make_logs():
	"""make strings for msgprint and errprint"""
	import json, conf
	from webnotes.utils import cstr
	if webnotes.error_log:
		# webnotes.response['exc'] = json.dumps("\n".join([cstr(d) for d in webnotes.error_log]))
		webnotes.response['exc'] = json.dumps([cstr(d) for d in webnotes.error_log])

	if webnotes.message_log:
		webnotes.response['_server_messages'] = json.dumps([cstr(d) for d in webnotes.message_log])
	
	if webnotes.debug_log and getattr(conf, "logging", False):
		webnotes.response['_debug_messages'] = json.dumps(webnotes.debug_log)

def print_cookie_header():
	"""if there ar additional cookies defined during the request, add them"""
	if webnotes.cookies or webnotes.add_cookies:
		for c in webnotes.add_cookies.keys():
			webnotes.cookies[c.encode('utf-8')] = \
				webnotes.add_cookies[c].encode('utf-8')

	if webnotes.cookies:
		print webnotes.cookies

def print_zip(response):
	response = response.encode('utf-8')
	orig_len = len(response)
	if accept_gzip() and orig_len>512:
		response = compressBuf(response)
		eprint("Content-Encoding: gzip")
		eprint("Original-Length: %d" % orig_len)
	
	eprint("Content-Length: %d" % len(response))
		
	eprint("")
	print response
	
def json_handler(obj):
	"""serialize non-serializable data for json"""
	import datetime
	
	# serialize date
	if isinstance(obj, (datetime.date, datetime.timedelta, datetime.datetime)):
		return unicode(obj)
	else:
		raise TypeError, """Object of type %s with value of %s is not JSON serializable""" % \
			(type(obj), repr(obj))

def accept_gzip():
	if "gzip" in os.environ.get("HTTP_ACCEPT_ENCODING", ""):
		return True

def compressBuf(buf):
	import gzip, cStringIO
	zbuf = cStringIO.StringIO()
	zfile = gzip.GzipFile(mode = 'wb',  fileobj = zbuf, compresslevel = 5)
	zfile.write(buf)
	zfile.close()
	return zbuf.getvalue()
