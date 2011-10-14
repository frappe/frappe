# patch manager
#---------------

import webnotes

def run(patch_list, overwrite = 0, log_exception=1, conn = '', db_name = '', root_pwd = ''):
	# db connection
	if not conn:
		connect_db(db_name, root_pwd)
	else:
		webnotes.conn = conn
	
	# session
	if not webnotes.session:
		webnotes.session = {'user':'Administrator'}

	# no patches on accounts
	if webnotes.conn.cur_db_name=='accounts':
		return
		
	# check if already applied
	if not overwrite:
		patch_list = check_already_applied_patch(patch_list)
			
	for p in patch_list:
		webnotes.conn.begin()
				
		# execute patch
		execute_patch(p, log_exception)
			
		# update patch log table
		webnotes.conn.sql("insert into `__PatchLog` (patch, applied_on) values (%s, now())", p)
		
		webnotes.conn.commit()
		
		print "Patch: %s applied successfully..." % p

#-----------------------------------------------------
def execute_patch(p, log_exception):
	if log_exception:
		try:
			exec('from patches import ' + p)
			eval(p).execute()
		except Exception, e:
			write_log()
			webnotes.conn.rollback()
			return
	else:
		exec('from patches import ' + p)
		eval(p).execute()
	
#-----------------------------------------------------
def check_already_applied_patch(patch_list):
	"""
		Remove if patch already applied
	"""
	webnotes.conn.sql("create table if not exists `__PatchLog` (patch TEXT, applied_on DATETIME)")
	
	already_patched = [d[0] for d in webnotes.conn.sql("select distinct patch from `__PatchLog`")]
	pending_patch = []
	
	for p in patch_list:
		if p not in already_patched:
			pending_patch.append(p)

	return pending_patch

#-----------------------------------------------------
def connect_db(db_name, pwd):
	"""
		Connect database
	"""
	import webnotes.db
	webnotes.conn = webnotes.db.Database(user='root', password=pwd)
	webnotes.conn.use(db_name)

#-----------------------------------------------------
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
