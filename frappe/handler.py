# Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt 

from __future__ import unicode_literals
import json
import frappe
import frappe.utils
import frappe.sessions
import frappe.utils.file_manager
import frappe.widgets.form.run_method
from frappe.utils.response import build_response, report_error

@frappe.whitelist(allow_guest=True)
def startup():
	frappe.response.update(frappe.sessions.get())

@frappe.whitelist()
def runserverobj(arg=None):
	frappe.widgets.form.run_method.runserverobj()

@frappe.whitelist(allow_guest=True)
def logout():
	frappe.local.login_manager.logout()

@frappe.whitelist(allow_guest=True)
def web_logout():
	frappe.local.login_manager.logout()
	frappe.conn.commit()
	frappe.repsond_as_web_page("Logged Out", """<p>You have been logged out.</p>
		<p><a href='index'>Back to Home</a></p>""")

@frappe.whitelist(allow_guest=True)
def run_custom_method(doctype, name, custom_method):
	"""cmd=run_custom_method&doctype={doctype}&name={name}&custom_method={custom_method}"""
	bean = frappe.bean(doctype, name)
	controller = bean.get_controller()
	if getattr(controller, custom_method, frappe._dict()).is_whitelisted:
		frappe.call(getattr(controller, custom_method), **frappe.local.form_dict)
	else:
		frappe.throw("Not Allowed")

@frappe.whitelist()
def uploadfile():
	try:
		if frappe.form_dict.get('from_form'):
			try:
				ret = frappe.utils.file_manager.upload()
			except frappe.DuplicateEntryError, e:
				# ignore pass
				ret = None
				frappe.conn.rollback()
		else:
			if frappe.form_dict.get('method'):
				ret = frappe.get_attr(frappe.form_dict.method)()
	except Exception, e:
		frappe.errprint(frappe.utils.get_traceback())
		ret = None

	return ret

def handle():
	"""handle request"""
	cmd = frappe.local.form_dict.cmd
	
	if cmd!='login':		
		status_codes = {
			frappe.PermissionError: 403,
			frappe.AuthenticationError: 401,
			frappe.DoesNotExistError: 404,
			frappe.SessionStopped: 503,
			frappe.OutgoingEmailError: 501
		}
		
		try:
			execute_cmd(cmd)
		except Exception, e:
			report_error(status_codes.get(e.__class__, 500))
		else:
			if frappe.local.request.method in ("POST", "PUT") and frappe.conn:
				frappe.conn.commit()
				
	build_response()

	if frappe.conn:
		frappe.conn.close()
	if frappe._memc:
		frappe._memc.disconnect_all()

def execute_cmd(cmd):
	"""execute a request as python module"""
	method = get_attr(cmd)

	# check if whitelisted
	if frappe.session['user'] == 'Guest':
		if (method not in frappe.guest_methods):
			raise frappe.PermissionError('Not Allowed, %s' % str(method))
	else:
		if not method in frappe.whitelisted:
			frappe._response.status_code = 403
			frappe.msgprint('Not Allowed, %s' % str(method))
			raise frappe.PermissionError('Not Allowed, %s' % str(method))
		
	ret = frappe.call(method, **frappe.form_dict)

	# returns with a message
	if ret:
		frappe.response['message'] = ret

	# update session
	if "session_obj" in frappe.local:
		frappe.local.session_obj.update()


def get_attr(cmd):
	"""get method object from cmd"""
	if '.' in cmd:
		method = frappe.get_attr(cmd)
	else:
		method = globals()[cmd]
	frappe.log("method:" + cmd)
	return method
