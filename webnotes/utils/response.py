# Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt 

from __future__ import unicode_literals
import json, inspect
import datetime
import gzip, cStringIO
import webnotes
import webnotes.utils
import webnotes.sessions
import webnotes.model.utils
from werkzeug.local import LocalProxy

def report_error(status_code):
	webnotes.errprint(webnotes.utils.get_traceback())
	webnotes._response.status_code = status_code
	if webnotes.request_method == "POST":
		webnotes.conn.rollback()

def build_response():
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
	webnotes._response.headers["Content-Type"] = "text/json; charset: utf-8"
	print_zip(json.dumps(webnotes.local.response, default=json_handler, separators=(',',':')))

def cleanup_docs():
	if webnotes.response.get('docs') and type(webnotes.response['docs'])!=dict:
		webnotes.response['docs'] = webnotes.model.utils.compress(webnotes.response['docs'])
		
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
	if webnotes.error_log:
		# webnotes.response['exc'] = json.dumps("\n".join([cstr(d) for d in webnotes.error_log]))
		webnotes.response['exc'] = json.dumps([webnotes.utils.cstr(d) for d in webnotes.local.error_log])

	if webnotes.local.message_log:
		webnotes.response['_server_messages'] = json.dumps([webnotes.utils.cstr(d) for d in webnotes.local.message_log])
	
	if webnotes.debug_log and webnotes.conf.get("logging") or False:
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
	zbuf = cStringIO.StringIO()
	zfile = gzip.GzipFile(mode = 'wb',  fileobj = zbuf, compresslevel = 5)
	zfile.write(buf)
	zfile.close()
	return zbuf.getvalue()
