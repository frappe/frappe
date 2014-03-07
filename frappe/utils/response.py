# Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt 

from __future__ import unicode_literals
import json
import datetime
import gzip, cStringIO
import mimetypes
import os
import frappe
from frappe import _
import frappe.utils
import frappe.sessions
import frappe.model.utils
from werkzeug.local import LocalProxy
from werkzeug.wsgi import wrap_file
from werkzeug.wrappers import Response
from werkzeug.exceptions import NotFound, Forbidden

def report_error(status_code):
	if status_code!=404 or frappe.conf.logging:
		frappe.errprint(frappe.utils.get_traceback())
	frappe._response.status_code = status_code
	if frappe.request_method == "POST":
		frappe.db.rollback()

def build_response():
	print_map = {
		'csv': print_csv,
		'download': print_raw,
		'json': print_json,
		'page': print_page,
		'redirect': redirect
	}
	
	print_map.get(frappe.response.get('type'), print_json)()

def print_page():
	"""print web page"""
	from frappe.website.render import render
	render(frappe.response['page_name'])

def print_json():
	make_logs()
	cleanup_docs()
	frappe._response.headers["Content-Type"] = "text/json; charset: utf-8"
	print_zip(json.dumps(frappe.local.response, default=json_handler, separators=(',',':')))
	
def redirect():
	frappe._response.data = """<!DOCTYPE HTML PUBLIC "-//W3C//DTD HTML 3.2 Final//EN">
		<title>Redirecting...</title>
		<h1>Redirecting...</h1>
		<p>You should be redirected automatically to target URL: <a href="{location}">/</a>.
		If not click the link.'""".format(location=frappe.response.location)
	
	frappe._response.headers["Content-Type"] = "text/html; charset: utf-8"
	frappe._response.status_code = frappe.response.status_code or 302
	frappe._response.location = frappe.response.location
	
def cleanup_docs():
	if frappe.response.get('docs') and type(frappe.response['docs'])!=dict:
		frappe.response['docs'] = frappe.model.utils.compress(frappe.response['docs'])
		
def print_csv():
	frappe._response.headers["Content-Type"] = \
		"text/csv; charset: utf-8"
	frappe._response.headers["Content-Disposition"] = \
		"attachment; filename=%s.csv" % frappe.response['doctype'].replace(' ', '_')
	frappe._response.data = frappe.response['result']

def print_raw():
	frappe._response.headers["Content-Type"] = \
		mimetypes.guess_type(frappe.response['filename'])[0] or "application/unknown"
	frappe._response.headers["Content-Disposition"] = \
		"filename=%s" % frappe.response['filename'].replace(' ', '_')
	frappe._response.data = frappe.response['filecontent']

def make_logs():
	"""make strings for msgprint and errprint"""
	if frappe.error_log:
		# frappe.response['exc'] = json.dumps("\n".join([cstr(d) for d in frappe.error_log]))
		frappe.response['exc'] = json.dumps([frappe.utils.cstr(d) for d in frappe.local.error_log])

	if frappe.local.message_log:
		frappe.response['_server_messages'] = json.dumps([frappe.utils.cstr(d) for d in frappe.local.message_log])
	
	if frappe.debug_log and frappe.conf.get("logging") or False:
		frappe.response['_debug_messages'] = json.dumps(frappe.local.debug_log)

def print_zip(response):
	response = response.encode('utf-8')
	orig_len = len(response)
	if accept_gzip() and orig_len>512:
		response = compressBuf(response)
		frappe._response.headers["Content-Encoding"] = "gzip"
	
	frappe._response.headers["Content-Length"] = str(len(response))
	frappe._response.data = response
	
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
	if "gzip" in frappe.get_request_header("HTTP_ACCEPT_ENCODING", ""):
		return True

def compressBuf(buf):
	zbuf = cStringIO.StringIO()
	zfile = gzip.GzipFile(mode = 'wb',  fileobj = zbuf, compresslevel = 5)
	zfile.write(buf)
	zfile.close()
	return zbuf.getvalue()

def download_backup(path):
	try:
		frappe.only_for(("System Manager", "Administrator"))
	except frappe.PermissionError:
		raise Forbidden(_("You need to be logged in and have System Manager Role to be able to access backups."))
	send_private_file(path)

def send_private_file(path):
	path = path[1:] if path.startswith('/') else path
	path = os.path.join(frappe.local.conf.get('private_path', 'private'), path)

	if frappe.local.request.headers.get('X-Use-X-Accel-Redirect'):
		path = '/' + path
		frappe.local._response.headers['X-Accel-Redirect'] = path
	else:
		filename = os.path.basename(path)
		filepath = frappe.utils.get_site_path(path)
		try:
			f = open(filepath, 'rb')
		except IOError:
			raise NotFound
		frappe.local._response = Response(wrap_file(frappe.local.request.environ, f))
		frappe.local._response.headers.add('Content-Disposition', 'attachment', filename=filename)
		frappe.local._response.headers['Content-Type'] = mimetypes.guess_type(filename)[0] or 'application/octet-stream'
