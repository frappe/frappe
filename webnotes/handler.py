# Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt 

from __future__ import unicode_literals
import json
import webnotes
import webnotes.utils
import webnotes.sessions
import webnotes.utils.file_manager
import webnotes.widgets.form.run_method
from webnotes.utils.response import build_response, report_error

@webnotes.whitelist(allow_guest=True)
def startup():
	webnotes.response.update(webnotes.sessions.get())

@webnotes.whitelist()
def runserverobj(arg=None):
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
		webnotes.call(getattr(controller, custom_method), **webnotes.local.form_dict)
	else:
		webnotes.throw("Not Allowed")

@webnotes.whitelist()
def uploadfile():
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
	cmd = webnotes.local.form_dict.cmd
	
	if cmd!='login':		
		status_codes = {
			webnotes.PermissionError: 403,
			webnotes.AuthenticationError: 401,
			webnotes.DoesNotExistError: 404,
			webnotes.SessionStopped: 503,
			webnotes.OutgoingEmailError: 501
		}
		
		try:
			execute_cmd(cmd)
		except Exception, e:
			report_error(status_codes.get(e.__class__, 500))
		else:
			if webnotes.local.request.method in ("POST", "PUT") and webnotes.conn:
				webnotes.conn.commit()
				
	build_response()

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
			raise webnotes.PermissionError('Not Allowed, %s' % str(method))
	else:
		if not method in webnotes.whitelisted:
			webnotes._response.status_code = 403
			webnotes.msgprint('Not Allowed, %s' % str(method))
			raise webnotes.PermissionError('Not Allowed, %s' % str(method))
		
	ret = webnotes.call(method, **webnotes.form_dict)

	# returns with a message
	if ret:
		webnotes.response['message'] = ret

	# update session
	if "session_obj" in webnotes.local:
		webnotes.local.session_obj.update()


def get_attr(cmd):
	"""get method object from cmd"""
	if '.' in cmd:
		method = webnotes.get_attr(cmd)
	else:
		method = globals()[cmd]
	webnotes.log("method:" + cmd)
	return method
