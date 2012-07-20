# Copyright (c) 2012 Web Notes Technologies Pvt Ltd (http://erpnext.com)
# 
# MIT License (MIT)
# 
# Permission is hereby granted, free of charge, to any person obtaining a 
# copy of this software and associated documentation files (the "Software"), 
# to deal in the Software without restriction, including without limitation 
# the rights to use, copy, modify, merge, publish, distribute, sublicense, 
# and/or sell copies of the Software, and to permit persons to whom the 
# Software is furnished to do so, subject to the following conditions:
# 
# The above copyright notice and this permission notice shall be included in 
# all copies or substantial portions of the Software.
# 
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, 
# INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A 
# PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT 
# HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF 
# CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE 
# OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
# 

from __future__ import unicode_literals
import sys, os
import webnotes
import webnotes.utils

form = webnotes.form
form_dict = webnotes.form_dict

sql = None
session = None
errdoc = ''
errdoctype = ''
errmethod = ''

def get_cgi_fields():
	"""make webnotes.form_dict from cgi field storage"""
	import cgi
	import webnotes
	from webnotes.utils import cstr
	
	# make the form_dict
	webnotes.form = cgi.FieldStorage(keep_blank_values=True)
	for key in webnotes.form.keys():
		webnotes.form_dict[key] = cstr(webnotes.form.getvalue(key))

# Logs

@webnotes.whitelist(allow_guest=True)
def startup():
	import webnotes
	import webnotes.session_cache

	webnotes.response.update(webnotes.session_cache.get())

def cleanup_docs():
	import webnotes.model.utils
	if webnotes.response.get('docs') and type(webnotes.response['docs'])!=dict:
		webnotes.response['docs'] = webnotes.model.utils.compress(webnotes.response['docs'])

# server calls
# ------------------------------------------------------------------------------------

@webnotes.whitelist()
def runserverobj(arg=None):
	import webnotes.widgets.form.run_method
	webnotes.widgets.form.run_method.runserverobj()

@webnotes.whitelist(allow_guest=True)
def logout():
	webnotes.login_manager.logout()


# DocType Mapper
# ------------------------------------------------------------------------------------

@webnotes.whitelist()
def dt_map():
	import webnotes
	import webnotes.model.utils
	from webnotes.model.code import get_obj
	from webnotes.model.doc import Document
	
	form_dict = webnotes.form_dict
	
	dt_list = webnotes.model.utils.expand(form_dict.get('docs'))
	from_doctype = form_dict.get('from_doctype')
	to_doctype = form_dict.get('to_doctype')
	from_docname = form_dict.get('from_docname')
	from_to_list = form_dict.get('from_to_list')
	
	dm = get_obj('DocType Mapper', from_doctype +'-' + to_doctype)
	dl = dm.dt_map(from_doctype, to_doctype, from_docname, Document(fielddata = dt_list[0]), [], from_to_list)
	
	webnotes.response['docs'] = dl

# Load Month Events
# ------------------------------------------------------------------------------------

@webnotes.whitelist()
def load_month_events():
	import webnotes

	mm = webnotes.form_dict.get('month')
	yy = webnotes.form_dict.get('year')
	m_st = str(yy) + '-' + str(mm) + '-01'
	m_end = str(yy) + '-' + str(mm) + '-31'

	import webnotes.widgets.event
	webnotes.response['docs'] = webnotes.widgets.event.get_cal_events(m_st, m_end)

# Data import
# ------------------------------------------------------------------------------------

@webnotes.whitelist()
def import_csv():
	import webnotes.model.import_docs
	from webnotes.utils import cint
	
	i = webnotes.model.import_docs.CSVImport()
	r = i.import_csv(webnotes.form_dict.get('csv_file'), webnotes.form_dict.get('dateformat'), webnotes.form_dict.get('overwrite', 0) and 1)
	
	webnotes.response['type']='iframe'
	rhead = '''<style>body, html {font-family: Arial; font-size: 12px;}</style>'''
	webnotes.response['result']= rhead + r

@webnotes.whitelist()
def get_template():
	import webnotes.model.import_docs
	webnotes.model.import_docs.get_template()
	

# File Upload
# ------------------------------------------------------------------------------------

@webnotes.whitelist()
def uploadfile():
	import webnotes.utils
	import webnotes.utils.file_manager
	import json

	ret = []

	try:
		if webnotes.form_dict.get('from_form'):
			webnotes.utils.file_manager.upload()
		else:
			if webnotes.form_dict.get('method'):
				m = webnotes.form_dict['method']
				modulename = '.'.join(m.split('.')[:-1])
				methodname = m.split('.')[-1]

				__import__(modulename)
				import sys
				moduleobj = sys.modules[modulename]
				ret = getattr(moduleobj, methodname)()
	except Exception, e:
		webnotes.msgprint(e)
		webnotes.errprint(webnotes.utils.getTraceback())

	webnotes.response['type'] = 'iframe'
	if not webnotes.response.get('result'):
		webnotes.response['result'] = """<script>
			window.parent.wn.upload.callback("%s", %s);
		</script>""" % (webnotes.form_dict.get('_id'),
			json.dumps(ret))

@webnotes.whitelist(allow_guest=True)
def reset_password():
	form_dict = webnotes.form_dict
	from webnotes.model.code import get_obj
	
	user = form_dict.get('user', '')
	if webnotes.conn.sql("""select name from tabProfile where name=%s""", user):
		import profile
		user_profile = profile.Profile(user)
		pwd = user_profile.reset_password()
		user_profile.send_new_pwd(pwd)
		
		webnotes.msgprint("Password has been reset and sent to your email id.")
	else:
		webnotes.msgprint("No such user (%s)" % user)


def handle():
	"""handle request"""
	cmd = webnotes.form_dict['cmd']

	if cmd!='login':
		# login executed in webnotes.auth
		try:
			execute_cmd(cmd)
		except webnotes.ValidationError, e:
			webnotes.errprint(e)
			webnotes.conn.rollback()
		except:
			webnotes.errprint(webnotes.utils.getTraceback())
			webnotes.conn and webnotes.conn.rollback()
			
	if webnotes.conn:
		webnotes.conn.close()
		
	print_response()

def execute_cmd(cmd):
	"""execute a request as python module"""
	validate_cmd(cmd)
	method = get_method(cmd)

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
		
	if not webnotes.conn.in_transaction:
		webnotes.conn.begin()

	if 'arg' in webnotes.form_dict:
		# direct method call
		ret = method(webnotes.form_dict.get('arg'))
	else:
		ret = method()

	# returns with a message
	if ret:
		webnotes.response['message'] = ret

	# update session
	webnotes.session_obj.update()

	if webnotes.conn.in_transaction:
		webnotes.conn.commit()

def get_method(cmd):
	"""get method object from cmd"""
	if '.' in cmd:
		from webnotes.utils import get_encoded_string
		cmd_parts = cmd.split('.')
		module_string = ".".join(cmd_parts[:-1])
		method_string = cmd_parts[-1]
		module = __import__(module_string,
				fromlist=[get_encoded_string(method_string)])
		method = getattr(module, method_string)
	else:
		method = globals()[cmd]
	return method
	
def validate_cmd(cmd):
	# check if there is no direct possibility of malicious script injection
	if cmd.startswith('webnotes.model.code'):
		raise Exception, 'Cannot call any methods from webnotes.model.code directly from the handler'

	if cmd.startswith('webnotes.model.db_schema'):
		raise Exception, 'Cannot call any methods from webnotes.model.db_schema directly from the handler'

	if cmd.startswith('webnotes.conn'):
		raise Exception, 'Cannot call database connection method directly from the handler'
		
def print_response():
	print_map = {
		'csv': print_csv,
		'iframe': print_iframe,
		'download': print_raw,
		'json': print_json,
	}
	
	print_map.get(webnotes.response.get('type'), print_json)()

def print_content(content, args=None):
	"""encode and print content"""
	if not args: args = {}
	
	from webnotes.utils import get_encoded_string
	print get_encoded_string("\n".join(content) % args)

def print_json():
	from webnotes.utils import get_encoded_string
	
	make_logs()
	cleanup_docs()
	add_cookies()

	content = []

	import json
	response = json.dumps(webnotes.response)
	response = get_encoded_string(response)
	response, content = gzip_response(response, content)

	content += [
		"Content-Type: text/html; charset: utf-8",
		"%(cookies)s",
		"",
	]
	
	args = { 'cookies': webnotes.cookies }
	
	print_content(content, args)

	# seperately printing response, since it can be gzipped or not
	print response
		
def print_csv():
	content = [
		"Content-Type: text/csv",
		"Content-Disposition: attachment; filename=%(filename)s.csv",
		"",
		"%(response)s"
	]
	
	args = {
		"filename": webnotes.response['doctype'].replace(' ', '_'),
		"response": webnotes.response['result'],
	}

	print_content(content, args)

def print_iframe():
	content = [
		"Content-Type: text/html",
		"",
		"%(response)s",
		"%(debug)s"
	]
	
	args = {
		'response': webnotes.response.get('result') or '',
		'debug': ''
	}
	
	if webnotes.debug_log:
		import json
		args['debug'] = """\
			<script>
				var messages = %(messages)s;
				if (messages.length) {
					for (var i in messages) {
						window.parent.msgprint(messages[i]);
					}
				}
				var errors = %(errors)s;
				if (errors.length) {
					for (var i in errors) {
						window.parent.console.log(errors[i]);
					}
				}
			</script>""" % {
				'messages': json.dumps(webnotes.message_log).replace("'", "\\'"),
				'errors': json.dumps(webnotes.debug_log).replace("'", "\\'"),
			}
	
	print_content(content, args)

def print_raw():
	content = [
		"Content-Type: %(mime_type)s",
		"Content-Disposition: filename=%(filename)s",
		"",
		"%(response)s",
	]
	
	import mimetypes
	args = {
		"mime_type": mimetypes.guess_type(webnotes.response['filename'])[0] \
						or 'application/unknown',
		"filename": webnotes.response['filename'].replace(' ', '_'),
		"content": webnotes.response['filecontent'],
	}
	
	print_content(content, args)

def make_logs():
	"""make strings for msgprint and errprint"""
	if webnotes.debug_log:
		t = '\n----------------\n'.join(webnotes.debug_log)
		webnotes.response['exc'] = t

	if webnotes.message_log:
		t = '\n----------------\n'.join(webnotes.message_log)
		webnotes.response['server_messages'] = t

def add_cookies():
	"""if there ar additional cookies defined during the request, add them"""
	from webnotes.utils import get_encoded_string
	if webnotes.cookies or webnotes.add_cookies:
		for c in webnotes.add_cookies.keys():
			webnotes.cookies[get_encoded_string(c)] = \
				get_encoded_string(webnotes.add_cookies[c])

def gzip_response(response, content):
	if accept_gzip() and len(response)>512:
		out_buf = compressBuf(response)
		content += [
			"Content-Encoding: gzip",
			"Content-Length: %d" % (len(out_buf))
		]
		response = out_buf
	return response, content
	
def accept_gzip():
	"""return true if client accepts gzip"""
	try:
		import string
		if string.find(os.environ["HTTP_ACCEPT_ENCODING"], "gzip") != -1:
			return True
		else:
			return False
	except:
		return False

def compressBuf(buf):
	import gzip, cStringIO
	zbuf = cStringIO.StringIO()
	zfile = gzip.GzipFile(mode = 'wb',  fileobj = zbuf, compresslevel = 5)
	zfile.write(buf)
	zfile.close()
	return zbuf.getvalue()
