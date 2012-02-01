"""
globals attached to webnotes module
+ some utility functions that should probably be moved
"""

code_fields_dict = {
	'Page':[('script', 'js'), ('content', 'html'), ('style', 'css'), ('static_content', 'html'), ('server_code', 'py')],
	'DocType':[('server_code_core', 'py'), ('client_script_core', 'js')],
	'Search Criteria':[('report_script', 'js'), ('server_script', 'py'), ('custom_query', 'sql')],
	'Patch':[('patch_code', 'py')],
	'Stylesheet':['stylesheet', 'css'],
	'Page Template':['template', 'html'],
	'Control Panel':[('startup_code', 'js'), ('startup_css', 'css')]
}

version = 'v170'
form_dict = {}
auth_obj = None
conn = None
form = None
session = None
user = None
is_testing = None
incoming_cookies = {}
add_cookies = {} # append these to outgoing request
cookies = {}
auto_masters = {}
tenant_id = None
response = {'message':'', 'exc':''}
debug_log = []
message_log = []


class ValidationError(Exception):
	pass

def getTraceback():
	import utils
	return utils.getTraceback()

def errprint(msg):
	"""
	   Append to the :data:`debug log`
	"""
	from utils import cstr
	debug_log.append(cstr(msg or ''))

def msgprint(msg, small=0, raise_exception=0, as_table=False):
	"""
	   Append to the :data:`message_log`
	"""	
	from utils import cstr
	if as_table and type(msg) in (list, tuple):
		msg = '<table border="1px" style="border-collapse: collapse" cellpadding="2px">' + ''.join(['<tr>'+''.join(['<td>%s</td>' % c for c in r])+'</tr>' for r in msg]) + '</table>'
	
	message_log.append((small and '__small:' or '')+cstr(msg or ''))
	if raise_exception:
		raise ValidationError

def is_apache_user():
	import os
	if os.environ.get('USER') == 'apache':
		return True 
	else:
		return (not os.environ.get('USER'))
		# os.environ does not have user, so allows a security vulnerability,fixed now. 

def get_index_path():
	import os
	return os.sep.join(os.path.dirname(os.path.abspath(__file__)).split(os.sep)[:-2])

def get_files_path():
	import defs
	if not conn:
		raise Exception, 'You must login first'

	if defs.files_path:
		return os.path.join(defs.files_path, conn.cur_db_name)
	else:
		return os.path.join(get_index_path(), 'user_files', conn.cur_db_name)
	
def create_folder(path):
	"""
	Wrapper function for os.makedirs (does not throw exception if directory exists)
	"""
	import os
	
	try:
		os.makedirs(path)
	except Exception, e:
		if e.args[0]==17: 
			pass
		else: 
			raise e

def connect(db_name=None):
	"""
		Connect to this db (or db), if called from command prompt
	"""
	if is_apache_user():
		raise Exception, 'Not for web users!'

	import webnotes.db
	global conn
	conn = webnotes.db.Database(user=db_name)
	
	global session
	session = {'user':'Administrator'}
	
	import webnotes.profile
	global user
	user = webnotes.profile.Profile('Administrator')	

def get_env_vars(env_var):
	import os
	return os.environ.get(env_var,'None')

remote_ip = get_env_vars('REMOTE_ADDR')		#Required for login from python shell
logger = None
	
def get_db_password(db_name):
	import defs
	
	if hasattr(defs, 'get_db_password'):
		return defs.get_db_password(db_name)
		
	elif hasattr(defs, 'db_password'):
		return defs.db_password
		
	else:
		return db_name