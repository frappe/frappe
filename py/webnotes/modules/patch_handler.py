"""
	Execute Patch Files

	Patch files usually lie in the "patches" module specified by "modules_path" in defs.py

	To run directly
	
	python lib/wnf.py patch patch1, patch2 etc
	python lib/wnf.py patch -f patch1, patch2 etc
	
	where patch1, patch2 is module name
"""
import webnotes

def run_all(patch_list=None):
	"""run all pending patches"""
	executed = [p[0] for p in webnotes.conn.sql("""select patch from __PatchLog""")]
	import patches.patch_list
	
	for patch in patch_list or patches.patch_list.patch_list:
		if not patch['patch_file'] in executed:
			pn = patch['patch_module'] + '.' + patch['patch_file']
			run_single(patchmodule = pn)

def reload_doc(args):
	"""relaod a doc args {module, doctype, docname}"""	
	import webnotes.modules.module_manager
	run_single(method = webnotes.modules.module_manager.reload_doc, methodargs = args)

def run_single(patchmodule=None, method=None, methodargs=None, force=False):
	"""run a single patch"""
	if force or method or not executed(patchmodule):
		execute_patch(patchmodule, method, methodargs)
		
def execute_patch(patchmodule, method=None, methodargs=None):
	"""execute the patch"""
	block_user(True)
	webnotes.conn.begin()
	log('Executing %s in %s' % (patchmodule or str(methodargs), webnotes.conn.cur_db_name))
	try:
		if patchmodule:
			patch = __import__(patchmodule, fromlist=True)
			getattr(patch, 'execute')()
			update_patch_log(patchmodule)
			log('Success')
		elif method:
			method(**methodargs)
			
		webnotes.conn.commit()		
	except Exception, e:
		webnotes.conn.rollback()
		global has_errors
		has_errors = True
		log(webnotes.getTraceback())

	block_user(False)

def update_patch_log(patchmodule):
	"""update patch_file in patch log"""
	webnotes.conn.sql("""INSERT INTO `__PatchLog` VALUES (%s, now())""", \
		patchmodule.split('.')[-1])

def executed(patchmodule):
	"""return True if is executed"""
	return webnotes.conn.sql("""select patch from __PatchLog where patch=%s""", patchmodule)
	
def block_user(block):
	"""stop/start execution till patch is run"""
	webnotes.conn.begin()
	msg = "Patches are being executed in the system. Please try again in a few moments."
	webnotes.conn.set_global('__session_status', block and 'stop' or None)
	webnotes.conn.set_global('__session_status_message', block and msg or None)
	webnotes.conn.commit()

def setup():
	webnotes.conn.sql("""CREATE TABLE IF NOT EXISTS `__PatchLog` (
			patch TEXT, applied_on DATETIME)""")
		
log_list = []
has_errors = False
def log(msg):
	log_list.append(msg)