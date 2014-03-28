# Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals
import frappe
from frappe import _
import frappe.model
import frappe.utils
import json, os

@frappe.whitelist()
def get(doctype, name=None, filters=None):
	if filters and not name:
		name = frappe.db.get_value(doctype, json.loads(filters))
		if not name:
			raise Exception, "No document found for given filters"
	return [d.fields for d in frappe.bean(doctype, name).doclist]

@frappe.whitelist()
def get_value(doctype, fieldname, filters=None, as_dict=True, debug=False):
	if not frappe.has_permission(doctype):
		frappe.msgprint("No Permission", raise_exception=True)
		
	if fieldname and fieldname.startswith("["):
		fieldname = json.loads(fieldname)
	return frappe.db.get_value(doctype, json.loads(filters), fieldname, as_dict=as_dict, debug=debug)

@frappe.whitelist()
def set_value(doctype, name, fieldname, value):
	if fieldname!="idx" and fieldname in frappe.model.default_fields:
		frappe.throw(_("Cannot edit standard fields"))
		
	doc = frappe.db.get_value(doctype, name, ["parenttype", "parent"], as_dict=True)
	if doc and doc.parent:
		bean = frappe.bean(doc.parenttype, doc.parent)
		child = bean.doclist.getone({"doctype": doctype, "name": name})
		child.set(fieldname, value)
	else:
		bean = frappe.bean(doctype, name)
		bean.set(fieldname, value)
		
	bean.save()
	
	return [d.fields for d in bean.doclist]

@frappe.whitelist()
def insert(doclist):
	if isinstance(doclist, basestring):
		doclist = json.loads(doclist)
		
	if isinstance(doclist, dict):
		doclist = [doclist]
		
	if doclist[0].get("parent") and doclist[0].get("parenttype"):
		# inserting a child record
		d = doclist[0]
		bean = frappe.bean(d["parenttype"], d["parent"])
		bean.append(d)
		bean.save()
		return [d]
	else:
		bean = frappe.bean(doclist).insert()
		return [d.fields for d in bean.doclist]

@frappe.whitelist()
def save(doclist):
	if isinstance(doclist, basestring):
		doclist = json.loads(doclist)

	bean = frappe.bean(doclist).save()
	return [d.fields for d in bean.doclist]
	
@frappe.whitelist()
def rename_doc(doctype, old_name, new_name, merge=False):
	new_name = frappe.rename_doc(doctype, old_name, new_name, merge=merge)
	return new_name

@frappe.whitelist()
def submit(doclist):
	if isinstance(doclist, basestring):
		doclist = json.loads(doclist)

	doclistobj = frappe.bean(doclist)
	doclistobj.submit()

	return [d.fields for d in doclist]

@frappe.whitelist()
def cancel(doctype, name):
	wrapper = frappe.bean(doctype, name)
	wrapper.cancel()
	
	return [d.fields for d in wrapper.doclist]

@frappe.whitelist()
def delete(doctype, name):
	frappe.delete_doc(doctype, name)

@frappe.whitelist()
def set_default(key, value, parent=None):
	"""set a user default value"""
	frappe.db.set_default(key, value, parent or frappe.session.user)
	frappe.clear_cache(user=frappe.session.user)

@frappe.whitelist()
def make_width_property_setter():
	doclist = json.loads(frappe.form_dict.doclist)
	if doclist[0]["doctype"]=="Property Setter" and doclist[0]["property"]=="width":
		bean = frappe.bean(doclist)
		bean.ignore_permissions = True
		bean.insert()

@frappe.whitelist()
def bulk_update(docs):
	docs = json.loads(docs)
	failed_docs = []
	for doc in docs:
		try:
			ddoc = {key: val for key, val in doc.iteritems() if key not in ['doctype', 'docname']}
			doctype = doc['doctype']
			docname = doc['docname']
			bean = frappe.bean(doctype, docname)
			bean.update(ddoc)
			bean.save()
		except:
			failed_docs.append({
				'doc': doc,
				'exc': frappe.utils.get_traceback()
			})
	return {'failed_docs': failed_docs}

@frappe.whitelist()
def has_permission(doctype, docname, perm_type="read"):
	# perm_type can be one of read, write, create, submit, cancel, report
	return {"has_permission": frappe.has_permission(doctype, perm_type.lower(), docname)}
	
@frappe.whitelist()
def get_js(src):
	contentpath = os.path.join(frappe.local.sites_path, src)
	with open(contentpath, "r") as srcfile:
		code = srcfile.read()
	
	if frappe.local.lang != "en":
		code += "\n\n$.extend(frappe._messages, {})".format(json.dumps(\
			frappe.get_lang_dict("jsfile", contentpath)))
	return code
	