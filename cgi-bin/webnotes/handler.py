import sys, os
import webnotes
import webnotes.defs
import webnotes.utils

form = webnotes.form
form_dict = webnotes.form_dict

sql = None
session = None
errdoc = ''
errdoctype = ''
errmethod = ''
fw_folder = '/Users/rushabh/workbench/www/'


# Logs

# refresh / start page
# ------------------------------------------------------------------------------------

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

def runserverobj(arg=None):
	import webnotes.widgets.form
	webnotes.widgets.form.runserverobj()

def logout():
	webnotes.login_manager.logout()

# DocType Mapper
# ------------------------------------------------------------------------------------

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

def load_month_events():
	import webnotes
	form = webnotes.form

	mm = form.getvalue('month')
	yy = form.getvalue('year')
	m_st = str(yy) + '-' + str(mm) + '-01'
	m_end = str(yy) + '-' + str(mm) + '-31'

	import webnotes.widgets.event
	webnotes.response['docs'] = webnotes.widgets.event.get_cal_events(m_st, m_end)

# Data import
# ------------------------------------------------------------------------------------

def import_csv():
	import webnotes.model.import_docs
	form = webnotes.form
	from webnotes.utils import cint
	
	i = webnotes.model.import_docs.CSVImport()
	r = i.import_csv(form.getvalue('csv_file'), form.getvalue('dateformat'), form_dict.get('overwrite', 0) and 1)
	
	webnotes.response['type']='iframe'
	rhead = '''<style>body, html {font-family: Arial; font-size: 12px;}</style>'''
	webnotes.response['result']= rhead + r

def get_template():
	import webnotes.model.import_docs
	webnotes.model.import_docs.get_template()
	

# File Upload
# ------------------------------------------------------------------------------------

def uploadfile():
	"""
		Save file as attachment
	"""
	from webnotes.utils.file_manager import save_as_attachment
	save_as_attachment()
	

# File download
# ------------------------------------------------------------------------------------
def get_file():
	import webnotes.utils.file_manager

	res = webnotes.utils.file_manager.get_file(form.getvalue('fname'))
	if res:
		webnotes.response['type'] = 'download'
		webnotes.response['filename'] = res[0]
		
		if hasattr(res[1], 'tostring'):
			webnotes.response['filecontent'] = res[1].tostring()
		else: 
			webnotes.response['filecontent'] = res[1]
	else:
		webnotes.msgprint('[get_file] Unknown file name')
		
# Get Graph
# ------------------------------------------------------------------------------------
def get_graph():
	form = webnotes.form

	import StringIO
	f = StringIO.StringIO()

	# call the object
	obj = server.get_obj(form_dict.get('dt'))
	plt = server.run_server_obj(obj, form_dict.get('method'), form_dict.get('arg'))
	plt.savefig(f)

	# stream out
	webnotes.response['type'] = 'download'
	webnotes.response['filename'] = webnotes.user.get_random_password() + '.png'
	webnotes.response['filecontent'] = f.getvalue()

# Reset Password
# ------------------------------------------------------------------------------------

def reset_password():
	form_dict = webnotes.form_dict
	
	act = form_dict.get('account', '')
	user = form_dict.get('user', '')
	if act:
		webnotes.conn.set_db(act)

	try:
		p = webnotes.profile.Profile(user)
		p.reset_password()
		webnotes.msgprint("Password has been reset and sent to your email id.")
	except Exception, e:
		webnotes.msgprint(str(e))

# Resume session
# ------------------------------------------------------------------------------------

def resume_session():
	webnotes.response['message'] = webnotes.session_obj.resume()

# -------------
# Create Backup
# -------------

def backupdb(form_dict, session):
	db_name = server.decrypt(form_dict.get('db_name'))

	server.backup_db(db_name)

	webnotes.response['type'] = 'download'
	webnotes.response['filename'] = db_name+'.tar.gz'
	webnotes.response['filecontent'] = open('../backups/' + db_name+'.tar.gz','rb').read()

# ---------------------------------------------------------------------

def validate_cmd(cmd):
	# check if there is no direct possibility of malicious script injection
	if cmd.startswith('webnotes.model.code'):
		raise Exception, 'Cannot call any methods from webnotes.model.code directly from the handler'

	if cmd.startswith('webnotes.model.db_schema'):
		raise Exception, 'Cannot call any methods from webnotes.model.db_schema directly from the handler'

	if cmd.startswith('webnotes.conn'):
		raise Exception, 'Cannot call database connection method directly from the handler'
	
# Execution Starts Here
# ---------------------------------------------------------------------

import webnotes.auth
import webnotes.db

# reset password
# ---------------------------------------------------------------------

if form_dict.has_key('cmd') and (form_dict.get('cmd')=='reset_password'):
	webnotes.conn = webnotes.db.Database(use_default = 1)
	sql = webnotes.conn.sql
	sql("START TRANSACTION")
	try:
		reset_password()
		sql("COMMIT")
	except Exception, e:
		webnotes.errprint(str(e))
		sql("ROLLBACK")
	
# pre-login access - for registration etc.
# ---------------------------------------------------------------------

elif form_dict.has_key('cmd') and (form_dict.get('cmd')=='prelogin'):
	webnotes.conn = webnotes.db.Database(use_default = 1)
	sql = webnotes.conn.sql
	webnotes.session = {'user':'Administrator'}

	import webnotes.model.code
	
	sql("START TRANSACTION")
	try:
		webnotes.response['message'] = webnotes.model.code.get_obj('Profile Control').prelogin(form_dict) or ''
		sql("COMMIT")
	except:
		webnotes.errprint(webnotes.utils.getTraceback())
		sql("ROLLBACK")

# main stuff
# ---------------------------------------------------------------------

else:

	try:
		webnotes.request = webnotes.auth.HTTPRequest()
	
		if form_dict.get('cmd') != 'login' and webnotes.conn:
			sql = webnotes.conn.sql
		
			# NOTE:
			# guest should only be allowed: 
			# getdoc (if Guest access)
			# runserverobj (if Guest access)
		
			# get command cmd
			cmd = form_dict.has_key('cmd') and form_dict.get('cmd') or ''
			read_only = form_dict.has_key('_read_only') and form_dict.get('_read_only') or None

			validate_cmd(cmd)

			module = ''
			if '.' in cmd:
				module = '.'.join(cmd.split('.')[:-1])
				cmd = cmd.split('.')[-1]

				exec 'from %s import %s' % (module, cmd) in locals()			
	
	
			# execute
			if locals().has_key(cmd):
				if (not webnotes.conn.in_transaction) and (not read_only):
					webnotes.conn.begin()
				
				if webnotes.form_dict.get('arg'):
					# direct method call
					ret = locals()[cmd](webnotes.form_dict.get('arg'))
				else:
					ret = locals()[cmd]()
				
				# returns with a message
				if ret:
					webnotes.response['message'] = ret
						
				# update session
				webnotes.session_obj.update()
				
				if webnotes.conn.in_transaction:
					webnotes.conn.commit()
			else:
				if cmd!='login':
					webnotes.msgprint('No Method: %s' % cmd)

	except webnotes.ValidationError:
		webnotes.conn.rollback()
	except:
		webnotes.errprint(webnotes.utils.getTraceback())
		webnotes.conn and webnotes.conn.rollback()
			

#### cleanup
#-----------

if webnotes.conn:
	webnotes.conn.close()

#### go

import string
import os

acceptsGzip, out_buf, str_out = 0, None, None
try:
	if string.find(os.environ["HTTP_ACCEPT_ENCODING"], "gzip") != -1:
		acceptsGzip = 1 # problem in win ?
except:
	pass

def compressBuf(buf):
	import gzip, cStringIO
	zbuf = cStringIO.StringIO()
	zfile = gzip.GzipFile(mode = 'wb',  fileobj = zbuf, compresslevel = 5)
	zfile.write(buf)
	zfile.close()
	return zbuf.getvalue()

# CSV
# -------------------------------------------------------------------

if webnotes.response.get('type')=='csv':
	print "Content-Type: text/csv"
	print "Content-Disposition: attachment; filename="+webnotes.response['doctype'].replace(' ', '_')+".csv"
	print
	print webnotes.response['result']

# IFRAME
# -------------------------------------------------------------------

elif webnotes.response.get('type')=='iframe':
	print "Content-Type: text/html"
	print
	if webnotes.response.get('result'):
		print webnotes.response['result']
	if webnotes.debug_log:
		print '''<script type='text/javascript'>alert("%s");</script>''' % ('-------'.join(webnotes.debug_log).replace('"', '').replace('\n',''))

# file
# -------------------------------------------------------------------

elif webnotes.response.get('type')=='download':
	import mimetypes
	print "Content-Type: %s" % (mimetypes.guess_type(webnotes.response['filename'])[0] or 'application/unknown')
	print "Content-Disposition: filename="+webnotes.response['filename'].replace(' ', '_')
	print
	print webnotes.response['filecontent']

# JSON
# -------------------------------------------------------------------

else:
	if webnotes.debug_log:
		save_log = 1
		if webnotes.debug_log[0].startswith('[Validation Error]'):
			save_log = 0

		t = '\n----------------\n'.join(webnotes.debug_log)
		if errdoctype: 
			t = t + '\nDocType: ' + errdoctype
		if errdoc: 
			t = t + '\nName: ' + errdoc
		if errmethod: 
			t = t + '\nMethod: ' + errmethod
		webnotes.response['exc'] = '<pre>'+t.replace('\n','<br>')+'</pre>'

		if save_log: # don't save validation errors
			try:  save_log(t, 'Server')
			except: pass

	if webnotes.message_log:
		webnotes.response['server_messages'] = '\n----------------\n'.join(webnotes.message_log)

	cleanup_docs()
	
	# Convert to JSON
	# ---------------
	try:
		import json
	except: # python 2.4
		import simplejson as json
	
	try:
		str_out = json.dumps(webnotes.response)
	except:
		str_out = str(webnotes.response).replace(', None', ', ""')
	
	if acceptsGzip and len(str_out)>512:
		out_buf = compressBuf(str_out)
		print "Content-Encoding: gzip"
		print "Content-Length: %d" % (len(out_buf))
		
	print "Content-Type: text/html; Charset: ISO-8859-1"
	
	# if there ar additional cookies defined during the request, add them here
	if webnotes.cookies or webnotes.add_cookies: 
		for c in webnotes.add_cookies.keys():
			webnotes.cookies[c] = webnotes.add_cookies[c]
			
		print webnotes.cookies
		
	print # Headers end
	
if out_buf:
	sys.stdout.write(out_buf)
elif str_out:
	print str_out
