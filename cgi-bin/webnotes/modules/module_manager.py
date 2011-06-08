#==============================================================================
# script to change the module name in the database & update svn
#==============================================================================

def change_module(dt, dn, from_module, to_module):
	import os, webnotes.defs
	from webnotes.modules import scrub
	
	# change in db
	webnotes.conn.sql("update `tab%s` set module=%s where name=%s" % (dt, '%s', '%s'), (to_module, dn))
	
	# export files
	from webnotes.modules.export_module import export_to_files
	export_to_files(record_list = [[dt, dn]])
	
	if dt in ['DocType','Page','Search Criteria']:
		dt, dn = scrub(dt), scrub(dn)
		
	# svn add
	webnotes.msgprint(os.popen("svn add %s" % os.path.join(webnotes.defs.modules_path, scrub(to_module), dt, dn)).read())

	# svn remove
	webnotes.msgprint(os.popen("svn remove %s" % os.path.join(webnotes.defs.modules_path, scrub(from_module), dt, dn)).read())



#==============================================================================
# SYNC
#==============================================================================
def reload_doc(module, dt, dn):
	"alias for webnotes.modules.import_module.import_file"
	from webnotes.modules.import_module import import_file

	import_file(module, dt, dn)

#
# get list of doctypes and their last update times
#
def get_doc_list(dt):
	"""
	returns the list of records and their last update times from the table
	if the column _last_update does not exist, it will add it to the table
	"""
	
	import webnotes
	module = dt=='Module Def' and 'name' or 'module'
	q = "select %s, name, _last_update from `tab%s`" % (module, dt)
	try:
		return webnotes.conn.sql(q)
	except Exception, e:
		if e.args[0]==1054:
			webnotes.conn.commit()
			webnotes.conn.sql("alter table `tab%s` add column _last_update varchar(32)" % dt)
			webnotes.conn.begin()
			return webnotes.conn.sql(q)
		elif e.args[0]==1146:
			return []
		else:
			raise e

#
# sync dt
#
def sync_one_doc(d, dt, ts):
	import webnotes
	from webnotes.model.db_schema import updatedb
	reload_doc(d[0], dt, d[1])
		
	# update schema(s)
	if dt=='DocType':
		updatedb(d[1])
	webnotes.conn.sql("update `tab%s` set _last_update=%s where name=%s" % (dt, '%s', '%s'), (ts, d[1]))

#
# sync doctypes, mappers and 
#
def sync_meta():
	import webnotes, os
	from webnotes.modules import scrub, get_module_path
	from webnotes.utils import cint

	tl = ['DocType', 'DocType Mapper', 'Module Def']

	for dt in tl:
		dtl = get_doc_list(dt)
				
		for d in filter(lambda x: x[0], dtl):
			try:
				ndt, ndn = dt, d[1]
				if dt == 'DocType':
					ndt, ndn = scrub(dt), scrub(d[1])
					
				mp = get_module_path(scrub(d[0]))
				ts = cint(os.stat(os.path.join(mp, ndt, ndn, ndn + '.txt')).st_mtime)
				
				if d[2] != str(ts):
					sync_one_doc(d, dt, ts)
			except OSError, e:
				pass






#==============================================================================
	
def get_module_details(m):
	from export_module import get_module_items
	return {'in_files': get_module_items_from_files(m), \
		'in_system':[[i[0], i[1], get_modified(i[0], i[1])] for i in get_module_items(m)]}

#==============================================================================

def get_modified(dt, dn):
	import webnotes
	try:
		return str(webnotes.conn.sql("select modified from `tab%s` where replace(name,' ','_')=%s" % (dt,'%s'), dn)[0][0])
	except:
		pass

#==============================================================================

def get_module_items_from_files(m):
	import os, webnotes.defs
	from import_module import listfolders

	items = []
	for item_type in listfolders(os.path.join(webnotes.defs.modules_path, m), 1):
		for item_name in listfolders(os.path.join(webnotes.defs.modules_path, m, item_type), 1):
			# read the file
			file = open(os.path.join(webnotes.defs.modules_path, m, item_type, item_name, item_name)+'.txt','r')
			doclist = eval(file.read())
			file.close()
			
			# append
			items.append([item_type, item_name, doclist[0]['modified']])
			
	return items

#==============================================================================
	
def get_last_update_for(mod):
	import webnotes
	try:
		return webnotes.conn.sql("select last_updated_date from `tabModule Def` where name=%s", mod)[0][0]
	except:
		return ''

#==============================================================================

def init_db_login(ac_name, db_name):
	import webnotes
	import webnotes.db
	import webnotes.profile
	
	if ac_name:
		webnotes.conn = webnotes.db.Database(ac_name = ac_name)
		webnotes.conn.use(webnotes.conn.user)
	elif db_name:
		webnotes.conn = webnotes.db.Database(user=db_name)
		webnotes.conn.use(db_name)
	else:
		webnotes.conn = webnotes.db.Database(use_default=1)
			
	webnotes.session = {'user':'Administrator'}
	webnotes.user = webnotes.profile.Profile()

#==============================================================================
# Return module names present in File System
#==============================================================================
def get_modules_from_filesystem():
	import os, webnotes.defs
	from import_module import listfolders
	
	modules = listfolders(webnotes.defs.modules_path, 1)
	out = []
	modules.sort()
	modules = filter(lambda x: x!='patches', modules)
	
	for m in modules:
		file = open(os.path.join(webnotes.defs.modules_path, m, 'module.info'), 'r')
		out.append([m, eval(file.read()), get_last_update_for(m), \
			webnotes.conn.exists('Module Def',m) and 'Installed' or 'Not Installed'])
		file.close()

	return out