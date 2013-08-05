# Copyright (c) 2013, Web Notes Technologies Pvt. Ltd.
# MIT License. See license.txt

from __future__ import unicode_literals
import webnotes
import json

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
