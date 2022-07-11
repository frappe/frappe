# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals

from werkzeug.wrappers import Response

import frappe
import frappe.sessions
import frappe.utils
from frappe import _, is_whitelisted
from frappe.core.doctype.server_script.server_script_utils import get_server_script_map
from frappe.utils import cint
from frappe.utils.csvutils import build_csv_response
from frappe.utils.response import build_response

ALLOWED_MIMETYPES = (
	"image/png",
	"image/jpeg",
	"application/pdf",
	"application/msword",
	"application/vnd.openxmlformats-officedocument.wordprocessingml.document",
	"application/vnd.ms-excel",
	"application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
	"application/vnd.oasis.opendocument.text",
	"application/vnd.oasis.opendocument.spreadsheet",
	"text/plain",
)


def handle():
	"""handle request"""

	cmd = frappe.local.form_dict.cmd
	data = None

	if cmd != "login":
		data = execute_cmd(cmd)

	# data can be an empty string or list which are valid responses
	if data is not None:
		if isinstance(data, Response):
			# method returns a response object, pass it on
			return data

		# add the response to `message` label
		frappe.response["message"] = data

	return build_response("json")


def execute_cmd(cmd, from_async=False):
	"""execute a request as python module"""
	for hook in frappe.get_hooks("override_whitelisted_methods", {}).get(cmd, []):
		# override using the first hook
		cmd = hook
		break

	# via server script
	server_script = get_server_script_map().get("_api", {}).get(cmd)
	if server_script:
		return run_server_script(server_script)

	try:
		method = get_attr(cmd)
	except Exception as e:
		frappe.throw(_("Failed to get method for command {0} with {1}").format(cmd, e))

	if from_async:
		method = method.queue

	if method != run_doc_method:
		is_whitelisted(method)
		is_valid_http_method(method)

	return frappe.call(method, **frappe.form_dict)


def run_server_script(server_script):
	response = frappe.get_doc("Server Script", server_script).execute_method()

	# some server scripts return output using flags (empty dict by default),
	# while others directly modify frappe.response
	# return flags if not empty dict (this overwrites frappe.response.message)
	if response != {}:
		return response


def is_valid_http_method(method):
	if frappe.flags.in_safe_exec:
		return

	http_method = frappe.local.request.method

	if http_method not in frappe.allowed_http_methods_for_whitelisted_func[method]:
		throw_permission_error()


def throw_permission_error():
	frappe.throw(_("Not permitted"), frappe.PermissionError)


@frappe.whitelist(allow_guest=True)
def version():
	return frappe.__version__


@frappe.whitelist(allow_guest=True)
def logout():
	frappe.local.login_manager.logout()
	frappe.db.commit()


@frappe.whitelist(allow_guest=True)
def web_logout():
	frappe.local.login_manager.logout()
	frappe.db.commit()
	frappe.respond_as_web_page(
		_("Logged Out"), _("You have been successfully logged out"), indicator_color="green"
	)


@frappe.whitelist()
def uploadfile():
	ret = None

	try:
		if frappe.form_dict.get("from_form"):
			try:
				ret = frappe.get_doc(
					{
						"doctype": "File",
						"attached_to_name": frappe.form_dict.docname,
						"attached_to_doctype": frappe.form_dict.doctype,
						"attached_to_field": frappe.form_dict.docfield,
						"file_url": frappe.form_dict.file_url,
						"file_name": frappe.form_dict.filename,
						"is_private": frappe.utils.cint(frappe.form_dict.is_private),
						"content": frappe.form_dict.filedata,
						"decode": True,
					}
				)
				ret.save()
			except frappe.DuplicateEntryError:
				# ignore pass
				ret = None
				frappe.db.rollback()
		else:
			if frappe.form_dict.get("method"):
				method = frappe.get_attr(frappe.form_dict.method)
				is_whitelisted(method)
				ret = method()
	except Exception:
		frappe.errprint(frappe.utils.get_traceback())
		frappe.response["http_status_code"] = 500
		ret = None

	return ret


@frappe.whitelist(allow_guest=True)
def upload_file():
	user = None
	if frappe.session.user == "Guest":
		if frappe.get_system_settings("allow_guests_to_upload_files"):
			ignore_permissions = True
		else:
			return
	else:
		user = frappe.get_doc("User", frappe.session.user)
		ignore_permissions = False

	files = frappe.request.files
	is_private = frappe.form_dict.is_private
	doctype = frappe.form_dict.doctype
	docname = frappe.form_dict.docname
	fieldname = frappe.form_dict.fieldname
	file_url = frappe.form_dict.file_url
	folder = frappe.form_dict.folder or "Home"
	method = frappe.form_dict.method
	filename = frappe.form_dict.file_name
	content = None

	if "file" in files:
		file = files["file"]
		content = file.stream.read()
		filename = file.filename

	frappe.local.uploaded_file = content
	frappe.local.uploaded_filename = filename

	if content is not None and (
		frappe.session.user == "Guest" or (user and not user.has_desk_access())
	):
		import mimetypes

		filetype = mimetypes.guess_type(filename)[0]
		if filetype not in ALLOWED_MIMETYPES:
			frappe.throw(_("You can only upload JPG, PNG, PDF, TXT or Microsoft documents."))

	if method:
		method = frappe.get_attr(method)
		is_whitelisted(method)
		return method()
	else:
		ret = frappe.get_doc(
			{
				"doctype": "File",
				"attached_to_doctype": doctype,
				"attached_to_name": docname,
				"attached_to_field": fieldname,
				"folder": folder,
				"file_name": filename,
				"file_url": file_url,
				"is_private": cint(is_private),
				"content": content,
			}
		)
		ret.save(ignore_permissions=ignore_permissions)
		return ret


def get_attr(cmd):
	"""get method object from cmd"""
	if "." in cmd:
		method = frappe.get_attr(cmd)
	else:
		method = globals()[cmd]
	frappe.log("method:" + cmd)
	return method


@frappe.whitelist(allow_guest=True)
def ping():
	return "pong"


def run_doc_method(method, docs=None, dt=None, dn=None, arg=None, args=None):
	"""run a whitelisted controller method"""
	import inspect
	import json

	if not args:
		args = arg or ""

	if dt:  # not called from a doctype (from a page)
		if not dn:
			dn = dt  # single
		doc = frappe.get_doc(dt, dn)

	else:
		if isinstance(docs, str):
			docs = json.loads(docs)

		doc = frappe.get_doc(docs)
		doc._original_modified = doc.modified
		doc.check_if_latest()

	if not doc or not doc.has_permission("read"):
		throw_permission_error()

	try:
		args = json.loads(args)
	except ValueError:
		args = args

	method_obj = getattr(doc, method)
	fn = getattr(method_obj, "__func__", method_obj)
	is_whitelisted(fn)
	is_valid_http_method(fn)

	fnargs = inspect.getfullargspec(method_obj).args

	if not fnargs or (len(fnargs) == 1 and fnargs[0] == "self"):
		response = doc.run_method(method)

	elif "args" in fnargs or not isinstance(args, dict):
		response = doc.run_method(method, args)

	else:
		response = doc.run_method(method, **args)

	frappe.response.docs.append(doc)
	if not response:
		return

	# build output as csv
	if cint(frappe.form_dict.get("as_csv")):
		build_csv_response(response, _(doc.doctype).replace(" ", ""))
		return

	frappe.response["message"] = response


# for backwards compatibility
runserverobj = run_doc_method
