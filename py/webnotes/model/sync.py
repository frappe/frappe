"""
	Sync's doctype and docfields from txt files to database
	perms will get synced only if none exist
"""
import webnotes

def sync_all():
	sync_core_doctypes()
	sync_modules()

def sync_core_doctypes():
	import os
	import core
	module_name = 'core'
	core_path = os.path.abspath(os.sep.join(core.__file__.split(os.sep)[:-1]
		+ ['doctype']))
	for path, folders, files in os.walk(core_path):
		for f in files:
			if f.endswith(".txt"):
				sync(module_name, f[:-4])

def sync_modules():
	import os
	import webnotes.defs
	for path, folders, files in os.walk(webnotes.defs.modules_path):
		if path == webnotes.defs.modules_path:
			modules_list = folders
		for f in files:
			if f.endswith(".txt"):
				rel_path = os.path.relpath(path, webnotes.defs.modules_path)
				path_tuple = rel_path.split(os.sep)
				if (len(path_tuple)==3 and path_tuple[0] in modules_list and
						path_tuple[1] == 'doctype'):
					#print (path_tuple[0], f[:-4])
					sync(path_tuple[0], f[:-4])

# docname in small letters with underscores
def sync(module_name, docname):
	with open(get_file_path(module_name, docname), 'r') as f:
		from webnotes.model.utils import peval_doclist
		doclist = peval_doclist(f.read())
		modified = doclist[0]['modified']
		if not doclist:
			raise Exception('DocList could not be evaluated')
		if modified == str(webnotes.conn.get_value('DocType', doclist[0].get('name'), 'modified')):
			return
		webnotes.conn.begin()
		
		delete_doctype_docfields(doclist)
		save_doctype_docfields(doclist)
		save_perms_if_none_exist(doclist)
		webnotes.conn.sql('UPDATE `tabDocType` SET modified=%s WHERE name=%s',
				(modified, doclist[0]['name']))
		
		webnotes.conn.commit()
		print module_name, '|', docname
		
		#raise Exception
		return doclist[0].get('name')
		
def get_file_path(module_name, docname):
	if not (module_name and docname):
		raise Exception('No Module Name or DocName specified')
	import os
	module = __import__(module_name)
	module_init_path = os.path.abspath(module.__file__)
	module_path = os.sep.join(module_init_path.split(os.sep)[:-1])
	return os.sep.join([module_path, 'doctype', docname, docname + '.txt'])

def delete_doctype_docfields(doclist):
	parent = doclist[0].get('name')
	if not parent: raise Exception('Could not determine parent')
	webnotes.conn.sql("DELETE FROM `tabDocType` WHERE name=%s", parent)
	webnotes.conn.sql("DELETE FROM `tabDocField` WHERE parent=%s", parent)

def save_doctype_docfields(doclist):
	from webnotes.model.doc import Document
	from webnotes.model.code import get_obj
	parent_doc = Document(fielddata=doclist[0])
	parent_doc.save(1, check_links=0,
			ignore_fields=1)
	idx = 1
	for d in doclist:
		if d.get('doctype') != 'DocField': continue
		d['idx'] = idx
		Document(fielddata=d).save(1, check_links=0, ignore_fields=1)
		idx += 1
	
	update_schema(parent_doc.name)

def update_schema(docname):
	from webnotes.model.db_schema import updatedb
	updatedb(docname)

	from webnotes.utils.cache import CacheItem
	CacheItem(docname).clear()

def save_perms_if_none_exist(doclist):
	res = webnotes.conn.sql("""SELECT name FROM `tabDocPerm`
			WHERE parent=%s""", doclist[0].get('name'))
	if res and res[0][0]: return

	from webnotes.model.doc import Document
	for d in doclist:
		if d.get('doctype') != 'DocPerm': continue
		Document(fielddata=d).save(1, check_links=0, ignore_fields=1)


import unittest
class TestSync(unittest.TestCase):
	def setUp(self):
		self.test_case = {
			'module_name': 'selling',
			'docname': 'sales_order'
		}
		webnotes.conn.begin()

	def tearDown(self):
		pass
		#from webnotes.utils import cstr
		#webnotes.conn.rollback()

	def test_sync(self):
		#old_doctype, old_docfields = self.query('Profile')
		#self.parent = sync(self.test_case.get('module_name'), self.test_case.get('docname'))
		#new_doctype, new_docfields = self.query(self.parent)
		#self.assertNotEqual(old_doctype, new_doctype)
		#self.assertNotEqual(old_docfields, new_docfields)

		#from webnotes.utils import cstr
		#print new_doctype[0]
		#print
		#print "\n".join((cstr(d) for d in new_docfields))
		#print "\n\n"
		pass

	def test_sync_all(self):
		sync_all()

	def query(self, parent):
		doctype = webnotes.conn.sql("SELECT name FROM `tabDocType` \
			WHERE name=%s", parent)
		docfields = webnotes.conn.sql("SELECT idx, fieldname, label, fieldtype FROM `tabDocField` \
			WHERE parent=%s order by idx", parent)
		#doctype = webnotes.conn.sql("SELECT * FROM `tabDocType` \
		#	WHERE name=%s", parent)
		#docfields = webnotes.conn.sql("SELECT * FROM `tabDocField` \
		#	WHERE parent=%s order by idx", parent)
		return doctype, docfields


