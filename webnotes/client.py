# Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals
import webnotes
from webnotes import _
import webnotes.model
import webnotes.utils
import json, os

@webnotes.whitelist()
def get(doctype, name=None, filters=None):
	if filters and not name:
		name = webnotes.conn.get_value(doctype, json.loads(filters))
		if not name:
			raise Exception, "No document found for given filters"
	return [d.fields for d in webnotes.bean(doctype, name).doclist]

@webnotes.whitelist()
def get_value(doctype, fieldname, filters=None, as_dict=True, debug=False):
	if not webnotes.has_permission(doctype):
		webnotes.msgprint("No Permission", raise_exception=True)
		
	if fieldname and fieldname.startswith("["):
		fieldname = json.loads(fieldname)
	return webnotes.conn.get_value(doctype, json.loads(filters), fieldname, as_dict=as_dict, debug=debug)

@webnotes.whitelist()
def set_value(doctype, name, fieldname, value):
	if fieldname in webnotes.model.default_fields:
		webnotes.throw(_("Cannot edit standard fields"))
		
	doc = webnotes.conn.get_value(doctype, name, ["parenttype", "parent"], as_dict=True)
	if doc and doc.parent:
		bean = webnotes.bean(doc.parenttype, doc.parent)
		child = bean.doclist.getone({"doctype": doctype, "name": name})
		child.fields[fieldname] = value
	else:
		bean = webnotes.bean(doctype, name)
		bean.doc.fields[fieldname] = value
		
	bean.save()
	
	return [d.fields for d in bean.doclist]

@webnotes.whitelist()
def insert(doclist):
	if isinstance(doclist, basestring):
		doclist = json.loads(doclist)
	
	doclist[0]["__islocal"] = 1
	return save(doclist)

@webnotes.whitelist()
def save(doclist):
	if isinstance(doclist, basestring):
		doclist = json.loads(doclist)

	doclistobj = webnotes.bean(doclist)
	doclistobj.save()
	
	return [d.fields for d in doclist]

@webnotes.whitelist()
def submit(doclist):
	if isinstance(doclist, basestring):
		doclist = json.loads(doclist)

	doclistobj = webnotes.bean(doclist)
	doclistobj.submit()

	return [d.fields for d in doclist]

@webnotes.whitelist()
def cancel(doctype, name):
	wrapper = webnotes.bean(doctype, name)
	wrapper.cancel()
	
	return [d.fields for d in wrapper.doclist]

@webnotes.whitelist()
def delete(doctype, name):
	webnotes.delete_doc(doctype, name)

@webnotes.whitelist()
def set_default(key, value, parent=None):
	"""set a user default value"""
	webnotes.conn.set_default(key, value, parent or webnotes.session.user)
	webnotes.clear_cache(user=webnotes.session.user)

@webnotes.whitelist()
def make_width_property_setter():
	doclist = json.loads(webnotes.form_dict.doclist)
	if doclist[0]["doctype"]=="Property Setter" and doclist[0]["property"]=="width":
		bean = webnotes.bean(doclist)
		bean.ignore_permissions = True
		bean.insert()

@webnotes.whitelist()
def bulk_update(docs):
	docs = json.loads(docs)
	failed_docs = []
	for doc in docs:
		try:
			ddoc = {key: val for key, val in doc.iteritems() if key not in ['doctype', 'docname']}
			doctype = doc['doctype']
			docname = doc['docname']
			bean = webnotes.bean(doctype, docname)
			bean.doc.update(ddoc)
			bean.save()
		except:
			failed_docs.append({
				'doc': doc,
				'exc': webnotes.utils.get_traceback()
			})
	return {'failed_docs': failed_docs}

@webnotes.whitelist()
def has_permission(doctype, docname, perm_type="read"):
	# perm_type can be one of read, write, create, submit, cancel, report
	return {"has_permission": webnotes.has_permission(doctype, perm_type.lower(), docname)}
	
@webnotes.whitelist()
def get_js(src):
	contentpath = os.path.join(webnotes.local.sites_path, src)
	with open(contentpath, "r") as srcfile:
		code = srcfile.read()
	
	if webnotes.local.lang != "en":
		code += "\n\n$.extend(wn._messages, {})".format(json.dumps(\
			webnotes.get_lang_dict("jsfile", contentpath)))
	return code
	