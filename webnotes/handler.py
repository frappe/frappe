# Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt 

from __future__ import unicode_literals
import sys, os
import webnotes
import webnotes.utils
import webnotes.sessions

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
	webnotes.local.login_manager.logout()

@webnotes.whitelist(allow_guest=True)
def web_logout():
	webnotes.local.login_manager.logout()
	webnotes.conn.commit()
	webnotes.repsond_as_web_page("Logged Out", """<p>You have been logged out.</p>
		<p><a href='index'>Back to Home</a></p>""")

@webnotes.whitelist(allow_guest=True)
def run_custom_method(doctype, name, custom_method):
	"""cmd=run_custom_method&doctype={doctype}&name={name}&custom_method={custom_method}"""
	bean = webnotes.bean(doctype, name)
	controller = bean.get_controller()
	if getattr(controller, custom_method, webnotes._dict()).is_whitelisted:
		call(getattr(controller, custom_method), webnotes.local.form_dict)
	else:
		webnotes.throw("Not Allowed")

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
				ret = webnotes.get_attr(webnotes.form_dict.method)()
	except Exception, e:
		webnotes.errprint(webnotes.utils.get_traceback())
		ret = None

	return ret

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
			webnotes.errprint(webnotes.utils.get_traceback())
			if webnotes.request_method == "POST":
				webnotes.conn.rollback()
		except webnotes.PermissionError, e:
			webnotes.errprint(webnotes.utils.get_traceback())
			webnotes.response['403'] = 1
			if webnotes.request_method == "POST":
				webnotes.conn.rollback()
		except:
			webnotes.errprint(webnotes.utils.get_traceback())
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
	method = get_attr(cmd)

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
	webnotes.local.session_obj.update()


def call(fn, args):
	import inspect

	if hasattr(fn, 'fnargs'):
		fnargs = fn.fnargs
	else:
		fnargs, varargs, varkw, defaults = inspect.getargspec(fn)

	newargs = {}
	for a in fnargs:
		if a in args:
			newargs[a] = args.get(a)
	return fn(**newargs)

def get_attr(cmd):
	"""get method object from cmd"""
	if '.' in cmd:
		method = webnotes.get_attr(cmd)
	else:
		method = globals()[cmd]
	webnotes.log("method:" + cmd)
	return method
			
def print_response():
	print_map = {
		'csv': print_csv,
		'download': print_raw,
		'json': print_json,
		'page': print_page
	}
	
	print_map.get(webnotes.response.get('type'), print_json)()

def print_page():
	"""print web page"""

	from webnotes.webutils import render
	render(webnotes.response['page_name'])

def print_json():	
	make_logs()
	cleanup_docs()

	webnotes._response.headers["Content-Type"] = "text/html; charset: utf-8"

	import json
	
	print_zip(json.dumps(webnotes.local.response, default=json_handler, separators=(',',':')))
		
def print_csv():
	webnotes._response.headers["Content-Type"] = \
		"text/csv; charset: utf-8"
	webnotes._response.headers["Content-Disposition"] = \
		"attachment; filename=%s.csv" % webnotes.response['doctype'].replace(' ', '_')
	webnotes._response.data = webnotes.response['result']

def print_raw():
	webnotes._response.headers["Content-Type"] = \
		mimetypes.guess_type(webnotes.response['filename'])[0] or "application/unknown"
	webnotes._response.headers["Content-Disposition"] = \
		"filename=%s" % webnotes.response['filename'].replace(' ', '_')
	webnotes._response.data = webnotes.response['filecontent']

def make_logs():
	"""make strings for msgprint and errprint"""
	import json
	from webnotes import conf
	from webnotes.utils import cstr
	if webnotes.error_log:
		# webnotes.response['exc'] = json.dumps("\n".join([cstr(d) for d in webnotes.error_log]))
		webnotes.response['exc'] = json.dumps([cstr(d) for d in webnotes.local.error_log])

	if webnotes.local.message_log:
		webnotes.response['_server_messages'] = json.dumps([cstr(d) for d in webnotes.local.message_log])
	
	if webnotes.debug_log and conf.get("logging") or False:
		webnotes.response['_debug_messages'] = json.dumps(webnotes.local.debug_log)

def print_zip(response):
	response = response.encode('utf-8')
	orig_len = len(response)
	if accept_gzip() and orig_len>512:
		response = compressBuf(response)
		webnotes._response.headers["Content-Encoding"] = "gzip"
	
	webnotes._response.headers["Content-Length"] = str(len(response))
	webnotes._response.data = response
	
def json_handler(obj):
	"""serialize non-serializable data for json"""
	import datetime
	from werkzeug.local import LocalProxy
	
	# serialize date
	if isinstance(obj, (datetime.date, datetime.timedelta, datetime.datetime)):
		return unicode(obj)
	elif isinstance(obj, LocalProxy):
		return unicode(obj)
	else:
		raise TypeError, """Object of type %s with value of %s is not JSON serializable""" % \
			(type(obj), repr(obj))

def accept_gzip():
	if "gzip" in webnotes.get_request_header("HTTP_ACCEPT_ENCODING", ""):
		return True

def compressBuf(buf):
	import gzip, cStringIO
	zbuf = cStringIO.StringIO()
	zfile = gzip.GzipFile(mode = 'wb',  fileobj = zbuf, compresslevel = 5)
	zfile.write(buf)
	zfile.close()
	return zbuf.getvalue()
