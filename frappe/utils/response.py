# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals
import json
import datetime
import mimetypes
import os
import frappe
from frappe import _
import frappe.model.document
import frappe.utils
import frappe.sessions
import werkzeug.utils
from werkzeug.local import LocalProxy
from werkzeug.wsgi import wrap_file
from werkzeug.wrappers import Response
from werkzeug.exceptions import NotFound, Forbidden
from frappe.core.doctype.file.file import check_file_permission
from frappe.website.render import render
from frappe.utils import cint
from six import text_type

def report_error(status_code):
	'''Build error. Show traceback in developer mode'''
	if (cint(frappe.db.get_system_setting('allow_error_traceback'))
		and (status_code!=404 or frappe.conf.logging)
		and not frappe.local.flags.disable_traceback):
		frappe.errprint(frappe.utils.get_traceback())

	response = build_response("json")
	response.status_code = status_code
	return response

def build_response(response_type=None):
	if "docs" in frappe.local.response and not frappe.local.response.docs:
		del frappe.local.response["docs"]

	response_type_map = {
		'csv': as_csv,
		'download': as_raw,
		'json': as_json,
		'page': as_page,
		'redirect': redirect,
		'binary': as_binary
	}

	return response_type_map[frappe.response.get('type') or response_type]()

def as_csv():
	response = Response()
	response.mimetype = 'text/csv'
	response.charset = 'utf-8'
	response.headers[b"Content-Disposition"] = ("attachment; filename=\"%s.csv\"" % frappe.response['doctype'].replace(' ', '_')).encode("utf-8")
	response.data = frappe.response['result']
	return response

def as_raw():
	response = Response()
	response.mimetype = frappe.response.get("content_type") or mimetypes.guess_type(frappe.response['filename'])[0] or b"application/unknown"
	response.headers[b"Content-Disposition"] = ("filename=\"%s\"" % frappe.response['filename'].replace(' ', '_')).encode("utf-8")
	response.data = frappe.response['filecontent']
	return response

def as_json():
	make_logs()
	response = Response()
	if frappe.local.response.http_status_code:
		response.status_code = frappe.local.response['http_status_code']
		del frappe.local.response['http_status_code']

	response.mimetype = 'application/json'
	response.charset = 'utf-8'
	response.data = json.dumps(frappe.local.response, default=json_handler, separators=(',',':'))
	return response

def as_binary():
	response = Response()
	response.mimetype = 'application/octet-stream'
	response.headers[b"Content-Disposition"] = ("filename=\"%s\"" % frappe.response['filename'].replace(' ', '_')).encode("utf-8")
	response.data = frappe.response['filecontent']
	return response

def make_logs(response = None):
	"""make strings for msgprint and errprint"""
	if not response:
		response = frappe.local.response

	if frappe.error_log:
		# frappe.response['exc'] = json.dumps("\n".join([cstr(d) for d in frappe.error_log]))
		response['exc'] = json.dumps([frappe.utils.cstr(d) for d in frappe.local.error_log])

	if frappe.local.message_log:
		response['_server_messages'] = json.dumps([frappe.utils.cstr(d) for
			d in frappe.local.message_log])

	if frappe.debug_log and frappe.conf.get("logging") or False:
		response['_debug_messages'] = json.dumps(frappe.local.debug_log)

	if frappe.flags.error_message:
		response['_error_message'] = frappe.flags.error_message

def json_handler(obj):
	"""serialize non-serializable data for json"""
	# serialize date
	if isinstance(obj, (datetime.date, datetime.timedelta, datetime.datetime)):
		return text_type(obj)

	elif isinstance(obj, LocalProxy):
		return text_type(obj)

	elif isinstance(obj, frappe.model.document.BaseDocument):
		doc = obj.as_dict(no_nulls=True)

		return doc

	elif type(obj)==type or isinstance(obj, Exception):
		return repr(obj)

	else:
		raise TypeError("""Object of type %s with value of %s is not JSON serializable""" % \
						(type(obj), repr(obj)))

def as_page():
	"""print web page"""
	return render(frappe.response['route'], http_status_code=frappe.response.get("http_status_code"))

def redirect():
	return werkzeug.utils.redirect(frappe.response.location)

def download_backup(path):
	try:
		frappe.only_for(("System Manager", "Administrator"))
	except frappe.PermissionError:
		raise Forbidden(_("You need to be logged in and have System Manager Role to be able to access backups."))

	return send_private_file(path)

def download_private_file(path):
	"""Checks permissions and sends back private file"""
	try:
		check_file_permission(path)

	except frappe.PermissionError:
		raise Forbidden(_("You don't have permission to access this file"))

	return send_private_file(path.split("/private", 1)[1])


def send_private_file(path):
	path = os.path.join(frappe.local.conf.get('private_path', 'private'), path.strip("/"))
	filename = os.path.basename(path)

	if frappe.local.request.headers.get('X-Use-X-Accel-Redirect'):
		path = '/protected/' + path
		response = Response()
		response.headers[b'X-Accel-Redirect'] = frappe.utils.encode(path)

	else:
		filepath = frappe.utils.get_site_path(path)
		try:
			f = open(filepath, 'rb')
		except IOError:
			raise NotFound

		response = Response(wrap_file(frappe.local.request.environ, f), direct_passthrough=True)

	# no need for content disposition and force download. let browser handle its opening.
	# response.headers.add(b'Content-Disposition', b'attachment', filename=filename.encode("utf-8"))

	response.mimetype = mimetypes.guess_type(filename)[0] or b'application/octet-stream'

	return response

def handle_session_stopped():
	frappe.respond_as_web_page(_("Updating"),
		_("Your system is being updated. Please refresh again after a few moments"),
		http_status_code=503, indicator_color='orange', fullpage = True, primary_action=None)
	return frappe.website.render.render("message", http_status_code=503)
