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
import bleach

@frappe.whitelist(allow_guest=True)
def version():
	return frappe.__version__

@frappe.whitelist()
def ping():
	return "pong"

@frappe.async.handler
def async_ping():
	return "pong"

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
	frappe.respond_as_web_page("Logged Out", """<p><a href="/index" class="text-muted">Back to Home</a></p>""")

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
		ret = None

	return ret

def handle():
	"""handle request"""
	cmd = frappe.local.form_dict.cmd

	if cmd!='login':
		execute_cmd(cmd)

	return build_response("json")

def execute_cmd(cmd, from_async=False):
	"""execute a request as python module"""
	for hook in frappe.get_hooks("override_whitelisted_methods", {}).get(cmd, []):
		# override using the first hook
		cmd = hook
		break

	method = get_attr(cmd)
	if from_async:
		method = method.queue

	is_whitelisted(method)

	ret = frappe.call(method, **frappe.form_dict)

	# returns with a message
	if ret:
		frappe.response['message'] = ret

def is_whitelisted(method):
	# check if whitelisted
	if frappe.session['user'] == 'Guest':
		if (method not in frappe.guest_methods):
			frappe.msgprint(_("Not permitted"))
			raise frappe.PermissionError('Not Allowed, {0}'.format(method))

		if method not in frappe.xss_safe_methods:
			# strictly sanitize form_dict
			# escapes html characters like <> except for predefined tags like a, b, ul etc.
			# if required, we can add more whitelisted tags like div, p, etc. (see its documentation)
			for key, value in frappe.form_dict.items():
				if isinstance(value, basestring):
					frappe.form_dict[key] = bleach.clean(value)

	else:
		if not method in frappe.whitelisted:
			frappe.msgprint(_("Not permitted"))
			raise frappe.PermissionError('Not Allowed, {0}'.format(method))

def get_attr(cmd):
	"""get method object from cmd"""
	if '.' in cmd:
		method = frappe.get_attr(cmd)
	else:
		method = globals()[cmd]
	frappe.log("method:" + cmd)
	return method


@frappe.whitelist()
def get_async_task_status(task_id):
	from frappe.celery_app import get_celery
	c = get_celery()
	a = c.AsyncResult(task_id)
	frappe.local.response['response'] = a.result
	return {
		"state": a.state,
		"progress": 0
	}
