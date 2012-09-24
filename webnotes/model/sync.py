from __future__ import unicode_literals
"""
	Sync's doctype and docfields from txt files to database
	perms will get synced only if none exist
"""
import webnotes

def sync_all(force=0):
	modules = []
	modules += sync_core_doctypes(force)
	modules += sync_modules(force)
	try:
		webnotes.conn.begin()
		webnotes.conn.sql("DELETE FROM __CacheItem")
		webnotes.conn.commit()
	except Exception, e:
		if e[0]!=1146: raise e
	return modules

def sync_core_doctypes(force=0):
	import os
	import core
	# doctypes
	return walk_and_sync(os.path.abspath(os.path.dirname(core.__file__)), force)

def sync_modules(force=0):
	import conf, os
	return walk_and_sync(os.path.join(os.path.dirname(conf.__file__), 'app'), force)

def walk_and_sync(start_path, force=0):
	"""walk and sync all doctypes and pages"""
	import os
	from webnotes.modules import reload_doc

	modules = []

	for path, folders, files in os.walk(start_path):
		for f in files:
			if f.endswith(".txt"):
				# great grand-parent folder is module_name
				module_name = path.split(os.sep)[-3]
				if not module_name in modules:
					modules.append(module_name)
				
				# grand parent folder is doctype
				doctype = path.split(os.sep)[-2]
				
				# parent folder is the name
				name = path.split(os.sep)[-1]
				
				if doctype == 'doctype':
					sync(module_name, name, force)
				elif doctype in ['page']:#, 'search_criteria', 'Print Format', 'DocType Mapper']:
					if reload_doc(module_name, doctype, name):
						print module_name + ' | ' + doctype + ' | ' + name
					
	return modules


# docname in small letters with underscores
def sync(module_name, docname, force=0):
	"""sync doctype from file if modified"""
	with open(get_file_path(module_name, docname), 'r') as f:
		from webnotes.model.utils import peval_doclist
		doclist = peval_doclist(f.read())
		modified = doclist[0]['modified']
		if not doclist:
			raise Exception('DocList could not be evaluated')
		if modified == str(webnotes.conn.get_value(doclist[0].get('doctype'), 
			doclist[0].get('name'), 'modified')) and not force:
			return
		webnotes.conn.begin()
		
		delete_doctype_docfields(doclist)
		save_doctype_docfields(doclist)
		save_perms_if_none_exist(doclist)
		webnotes.conn.sql("""UPDATE `tab{doctype}` 
			SET modified=%s WHERE name=%s""".format(doctype=doclist[0]['doctype']),
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

def sync_install(force=1):
	# sync all doctypes
	modules = sync_all(force)
	
	# load install docs
	load_install_docs(modules)

def load_install_docs(modules):
	import os
	if isinstance(modules, basestring): modules = [modules]
	
	for module_name in modules:
		module = __import__(module_name)
		if hasattr(module, 'install_docs'):
			webnotes.conn.begin()

			for data in module.install_docs:
				if data.get('name'):
					if not webnotes.conn.exists(data['doctype'], data.get('name')):
						create_doc(data)
				elif not webnotes.conn.exists(data):
					create_doc(data)
			
			webnotes.conn.commit()
			
		if hasattr(module, 'module_init'):
			module.module_init()

def create_doc(data):
	from webnotes.model.doc import Document
	d = Document(data['doctype'])
	d.fields.update(data)
	d.save()
	print 'Created %(doctype)s %(name)s' % d.fields

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


