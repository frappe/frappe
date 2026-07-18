# Copyright (c) 2022, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

import os
from mimetypes import guess_type
from pathlib import Path
from typing import TYPE_CHECKING

from werkzeug.wrappers import Response

import frappe
import frappe.sessions
import frappe.utils
from frappe import _, is_whitelisted, ping
from frappe.core.doctype.file.utils import find_file_by_url, get_safe_file_name
from frappe.core.doctype.server_script.server_script_utils import get_server_script_map
from frappe.monitor import add_data_to_monitor
from frappe.permissions import check_doctype_permission
from frappe.utils import cint, get_files_path
from frappe.utils.csvutils import build_csv_response
from frappe.utils.deprecations import deprecated
from frappe.utils.image import optimize_image
from frappe.utils.response import build_response

if TYPE_CHECKING:
	from frappe.core.doctype.file.file import File
	from frappe.core.doctype.user.user import User


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


def execute_cmd(cmd, from_async=False):
	"""execute a request as python module"""
	cmd = frappe.override_whitelisted_method(cmd)

	# via server script
	server_script = get_server_script_map().get("_api", {}).get(cmd)
	if server_script:
		return run_server_script(server_script)

	try:
		method = get_attr(cmd)
	except Exception as e:
		frappe.throw(_("Failed to get method for command {0} with {1}").format(cmd, str(e)))

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

	# Skip HTTP method validation when running in a background job
	if hasattr(frappe.local, "job"):
		return

	http_method = frappe.local.request.method

	if http_method not in frappe.allowed_http_methods_for_whitelisted_func[method]:
		frappe.throw_permission_error()


# `logout` and `web_logout` moved to frappe.core.api.auth. Plain import
# aliases (not lazy __getattr__) because the deprecated bare-cmd shorthand
# (`/api/method/logout`) resolves through this module's globals().
from frappe.core.api.auth import logout, web_logout

# `upload_file` and `download_file` (and their helpers) moved to
# frappe.core.api.file. Plain import aliases (not lazy __getattr__) because the
# deprecated bare-cmd shorthand (`/api/method/upload_file`) resolves through
# this module's globals().
from frappe.core.api.file import (
	ALLOWED_MIMETYPES,
	check_write_permission,
	download_file,
	upload_file,
)


def get_attr(cmd):
	"""get method object from cmd"""
	if "." in cmd:
		method = frappe.get_attr(cmd)
	else:
		from frappe.deprecation_dumpster import deprecation_warning

		deprecation_warning(
			"unknown",
			"v17",
			f"Calling shorthand for {cmd} is deprecated, please specify full path in RPC call.",
		)
		method = globals()[cmd]
	return method


def run_doc_method(method, docs=None, dt=None, dn=None, arg=None, args=None):
	"""run a whitelisted controller method"""
	from inspect import signature

	if not args and arg:
		args = arg

	if dt:  # not called from a doctype (from a page)
		if not dn:
			dn = dt  # single

		if not isinstance(dn, str | int):
			frappe.throw("'dn' must be a string or an integer")

		doc = frappe.get_doc(dt, dn, check_permission=True)

	else:
		docs = frappe.parse_json(docs)
		doc = frappe.get_doc(docs, check_permission=True)
		doc._original_modified = doc.modified
		doc.check_if_latest()

	if not doc:
		frappe.throw_permission_error()

	try:
		args = frappe.parse_json(args)
	except ValueError:
		pass

	method_obj = getattr(doc, method)
	fn = getattr(method_obj, "__func__", method_obj)
	is_whitelisted(fn)
	is_valid_http_method(fn)

	fnargs = list(signature(method_obj).parameters)

	if not fnargs or (len(fnargs) == 1 and fnargs[0] == "self"):
		response = doc.run_method(method)

	elif "args" in fnargs or not isinstance(args, dict):
		response = doc.run_method(method, args)

	else:
		response = doc.run_method(method, **args)

	doc.apply_fieldlevel_read_permissions()
	frappe.response.docs.append(doc)
	if response is None:
		return

	# build output as csv
	if cint(frappe.form_dict.get("as_csv")):
		build_csv_response(response, _(doc.doctype).replace(" ", ""))
		return

	frappe.response["message"] = response

	add_data_to_monitor(methodname=method)


runserverobj = deprecated(run_doc_method)
