from __future__ import unicode_literals
"""
	Sync's doctype and docfields from txt files to database
	perms will get synced only if none exist
"""
import webnotes
import os
import conf
from webnotes.modules import reload_doc

def sync_all(force=0):
	sync_from("lib", force)
	sync_from("app", force)
	webnotes.clear_cache()

def sync_for(folder, force=0, sync_everything = False):
	return walk_and_sync(os.path.join(os.path.dirname(os.path.abspath(conf.__file__)), 
		folder), force, sync_everything)

def walk_and_sync(start_path, force=0, sync_everything = False):
	"""walk and sync all doctypes and pages"""

	modules = []
	
	document_type = ['doctype', 'page', 'report']

	for path, folders, files in os.walk(start_path):
		if sync_everything or (os.path.basename(os.path.dirname(path)) in document_type):
			for f in files:
				if f.endswith(".txt"):
					doc_name = f.split(".txt")[0]
					if doc_name == os.path.basename(path):

						module_name = path.split(os.sep)[-3]
						doctype = path.split(os.sep)[-2]
						name = path.split(os.sep)[-1]
												
						if doctype == 'doctype':
							sync_doctype(module_name, name, force)
						else:
							if reload_doc(module_name, doctype, name, force):
								print module_name + ' | ' + doctype + ' | ' + name
					
	return modules


# docname in small letters with underscores
def sync_doctype(module_name, docname, force=0):
	"""sync doctype from file if modified"""
	with open(get_file_path(module_name, docname), 'r') as f:
		from webnotes.modules.utils import peval_doclist
		doclist = peval_doclist(f.read())
		
		if merge_doctype(doclist, force):
			print module_name, '|', docname
		
		#raise Exception
		return doclist[0].get('name')

def merge_doctype(doclist, force=False):
	modified = doclist[0]['modified']
	if not doclist:
		raise Exception('ModelWrapper could not be evaluated')

	db_modified = str(webnotes.conn.get_value(doclist[0].get('doctype'),
		doclist[0].get('name'), 'modified'))
		
	if modified == db_modified and not force:
		return

	webnotes.conn.begin()
	
	delete_doctype_docfields(doclist)
	save_doctype_docfields(doclist)
	save_perms_if_none_exist(doclist)
	webnotes.conn.sql("""UPDATE `tab{doctype}` 
		SET modified=%s WHERE name=%s""".format(doctype=doclist[0]['doctype']),
			(modified, doclist[0]['name']))
	
	webnotes.conn.commit()
	return True

def get_file_path(module_name, docname):
	if not (module_name and docname):
		raise Exception('No Module Name or DocName specified')
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

	webnotes.clear_cache(doctype=docname)

def save_perms_if_none_exist(doclist):
	if not webnotes.conn.sql("""select count(*) from tabDocPerm 
		where parent=%s""", doclist[0].name)[0][0]:
		for d in doclist:
			if d.get('doctype') != 'DocPerm': continue
			webnotes.doc(fielddata=d).save(1, check_links=0, ignore_fields=1)
