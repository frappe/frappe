# patch manager

def run(log_exception=1):
	import webnotes
	from patches import patch
	from webnotes.utils import cint
	
	next_patch = cint(webnotes.conn.get_global('next_patch'))
	
	if next_patch <= patch.last_patch:
		for i in range(next_patch, patch.last_patch+1):
			webnotes.conn.begin()
			if log_exception:
				try:
					patch.execute(i)
				except Exception, e:
					write_log()	
					return
			else:
				patch.execute(i)

			webnotes.conn.set_global('next_patch', str(i+1))
			webnotes.conn.commit()

def write_log():
	import os
	import webnotes.defs
	import webnotes
	
	patch_log = open(os.path.join(webnotes.defs.modules_path, 'patches', 'patch.log'), 'a')
	patch_log.write(('\n\nError in %s:\n' % webnotes.conn.cur_db_name) + webnotes.getTraceback())
	patch_log.close()
	
	webnotes.msgprint("There were errors in running patches, please call the Administrator")
	
	
