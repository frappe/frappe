# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals
import frappe
from frappe import _
import frappe.utils
import frappe.async
import frappe.sessions
import frappe.utils.file_manager
import frappe.desk.form.run_method
from frappe.utils.response import build_response
from werkzeug.wrappers import Response
from six import string_types

def handle():
	"""handle request"""
	cmd = frappe.local.form_dict.cmd
	data = None

	if cmd!='login':
		data = execute_cmd(cmd)

	if data:
		if isinstance(data, Response):
			# method returns a response object, pass it on
			return data

		# add the response to `message` label
		frappe.response['message'] = data

	return build_response("json")

def execute_cmd(cmd, from_async=False):
	"""execute a request as python module"""
	for hook in frappe.get_hooks("override_whitelisted_methods", {}).get(cmd, []):
		# override using the first hook
		cmd = hook
		break

	try:
		method = get_attr(cmd)
	except:
		frappe.respond_as_web_page(title='Invalid Method', html='Method not found',
			indicator_color='red', http_status_code=404)
		return

	if from_async:
		method = method.queue

	is_whitelisted(method)

	return frappe.call(method, **frappe.form_dict)


def is_whitelisted(method):
	# check if whitelisted
	if frappe.session['user'] == 'Guest':
		if (method not in frappe.guest_methods):
			frappe.msgprint(_("Not permitted"))
			raise frappe.PermissionError('Not Allowed, {0}'.format(method))

		if method not in frappe.xss_safe_methods:
			# strictly sanitize form_dict
			# escapes html characters like <> except for predefined tags like a, b, ul etc.
			for key, value in frappe.form_dict.items():
				if isinstance(value, string_types):
					frappe.form_dict[key] = frappe.utils.sanitize_html(value)

	else:
		if not method in frappe.whitelisted:
			frappe.msgprint(_("Not permitted"))
			raise frappe.PermissionError('Not Allowed, {0}'.format(method))

@frappe.whitelist(allow_guest=True)
def version():
	return frappe.__version__

@frappe.whitelist()
def runserverobj(method, docs=None, dt=None, dn=None, arg=None, args=None):
	frappe.desk.form.run_method.runserverobj(method, docs=docs, dt=dt, dn=dn, arg=arg, args=args)

@frappe.whitelist(allow_guest=True)
def logout():
	frappe.local.login_manager.logout()
	frappe.db.commit()

@frappe.whitelist(allow_guest=True)
def web_logout():
	frappe.local.login_manager.logout()
	frappe.db.commit()
	frappe.respond_as_web_page(_("Logged Out"), _("You have been successfully logged out"),
		indicator_color='green')

@frappe.whitelist(allow_guest=True)
def run_custom_method(doctype, name, custom_method):
	"""cmd=run_custom_method&doctype={doctype}&name={name}&custom_method={custom_method}"""
	doc = frappe.get_doc(doctype, name)
	if getattr(doc, custom_method, frappe._dict()).is_whitelisted:
		frappe.call(getattr(doc, custom_method), **frappe.local.form_dict)
	else:
		frappe.throw(_("Not permitted"), frappe.PermissionError)

@frappe.whitelist()
def uploadfile():
	try:
		if frappe.form_dict.get('from_form'):
			try:
				ret = frappe.utils.file_manager.upload()
			except frappe.DuplicateEntryError:
				# ignore pass
				ret = None
				frappe.db.rollback()
		else:
			if frappe.form_dict.get('method'):
				method = frappe.get_attr(frappe.form_dict.method)
				is_whitelisted(method)
				ret = method()
	except Exception:
		frappe.errprint(frappe.utils.get_traceback())
		frappe.response['http_status_code'] = 500
		ret = None

	return ret


def get_attr(cmd):
	"""get method object from cmd"""
	if '.' in cmd:
		method = frappe.get_attr(cmd)
	else:
		method = globals()[cmd]
	frappe.log("method:" + cmd)
	return method

@frappe.whitelist()
def ping():
	return "pong"
