"""
	Execute patch files.
	
	Patch files must be in the "patches" module specified by "modules_path"
	To run directly
	
	python lib/wnf.py patch patch1, patch2 etc
	python lib/wnf.py patch -f patch1, patch2 etc
	
	where patch1, patch2 is module name
"""


def run(patch_list, overwrite = 0, log_exception=1, conn = '', db_name = '', db_password = ''):
	import webnotes, webnotes.defs
	
	print patch_list

	# db connection
	if not conn:
		connect_db(db_name or webnotes.defs.default_db_name, \
			db_password or webnotes.defs.db_password)
	else:
		webnotes.conn = conn
	
	# session
	if not (webnotes.session and webnotes.session['user']):
		webnotes.session = {'user':'Administrator'}

	# no patches on accounts
	if webnotes.conn.cur_db_name=='accounts':
		return
	
	# check if already applied
	if not overwrite:
		patch_list = check_already_applied_patch(patch_list)
	
	block_user("Patches are being executed, please try again in a few minutes")

	try:
		for p in patch_list:
			# execute patch
			execute_patch(p, log_exception)
	
	except Exception, e:
		webnotes.conn.rollback()
		if log_exception:
			write_log()
		else:
			print webnotes.getTraceback()
	finally:
		# unblock
		block_user()

def block_user(msg=None):
	"""stop further executions till patch is run"""
	import webnotes
	webnotes.conn.begin()
	webnotes.conn.set_global('__session_status', msg and 'stop' or None)
	webnotes.conn.set_global('__session_status_message', msg or None)
	webnotes.conn.commit()


def execute_patch(p, log_exception):
	import webnotes

	webnotes.conn.begin()

	exec('import ' + p)
	eval(p).execute()

	# update patch log table
	webnotes.conn.sql("insert into `__PatchLog` (patch, applied_on) values (%s, now())", p)

	webnotes.conn.commit()

	print "Patch: %s applied successfully..." % p

def check_already_applied_patch(patch_list):
	"""
		Remove if patch already applied
	"""
	import webnotes
	
	try:
		already_patched = [d[0] for d in webnotes.conn.sql("select distinct patch from `__PatchLog`")]
	except Exception, e:
		if e.args[0]==1146:
			webnotes.conn.sql("create table if not exists `__PatchLog` (patch TEXT, applied_on DATETIME)")
			check_already_applied_patch(patch_list)
			return
		else:
			raise e
			
	pending_patch = []
	
	for p in patch_list:
		if p not in already_patched:
			pending_patch.append(p)

	return pending_patch

def connect_db(db_name, pwd):
	"""
		Connect database
	"""
	import webnotes
	import webnotes.db
	webnotes.conn = webnotes.db.Database(user=db_name, password=pwd)
	webnotes.conn.use(db_name)


def write_log():
	import os
	import webnotes.defs
	import webnotes
	
	patch_log = open(os.path.join(webnotes.defs.modules_path, 'patches', 'patch.log'), 'a')
	patch_log.write(('\n\nError in %s:\n' % webnotes.conn.cur_db_name) + webnotes.getTraceback())
	patch_log.close()
	
	if getattr(webnotes.defs,'admin_email_notification',0):
		from webnotes.utils import sendmail
		subj = 'Patch Error. <br>Account: %s' % webnotes.conn.cur_db_name
		msg = subj + '<br><br>' + webnotes.getTraceback()
		print msg
		#sendmail(['nabin@erpnext.com'], sender='automail@erpnext.com', subject= subj, parts=[['text/plain', msg]])

if __name__=='__main__':
	import sys, os

	# webnotes path
	sys.path.append('lib/py')
	
	run(sys.argv[1:])
