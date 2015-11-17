# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals
import frappe
from frappe import _
import frappe.model
import frappe.utils
import json, os

@frappe.whitelist()
def get_list(doctype, fields=None, filters=None, order_by=None,
	limit_start=None, limit_page_length=20):
	return frappe.get_list(doctype, fields=fields, filters=filters, order_by=order_by,
		limit_start=limit_start, limit_page_length=limit_page_length, ignore_permissions=False)

@frappe.whitelist()
def get(doctype, name=None, filters=None):
	if filters and not name:
		name = frappe.db.get_value(doctype, json.loads(filters))
		if not name:
			raise Exception, "No document found for given filters"

	doc = frappe.get_doc(doctype, name)
	if not doc.has_permission("read"):
		raise frappe.PermissionError

	return frappe.get_doc(doctype, name).as_dict()

@frappe.whitelist()
def get_value(doctype, fieldname, filters=None, as_dict=True, debug=False):
	if not frappe.has_permission(doctype):
		frappe.throw(_("Not permitted"), frappe.PermissionError)

	try:
		filters = json.loads(filters)
	except ValueError:
		# name passed, not json
		pass

	try:
		fieldname = json.loads(fieldname)
	except ValueError:
		# name passed, not json
		pass

	return frappe.db.get_value(doctype, filters, fieldname, as_dict=as_dict, debug=debug)

@frappe.whitelist()
def set_value(doctype, name, fieldname, value):
	if fieldname!="idx" and fieldname in frappe.model.default_fields:
		frappe.throw(_("Cannot edit standard fields"))

	doc = frappe.db.get_value(doctype, name, ["parenttype", "parent"], as_dict=True)
	if doc and doc.parent and doc.parenttype:
		doc = frappe.get_doc(doc.parenttype, doc.parent)
		child = doc.getone({"doctype": doctype, "name": name})
		child.set(fieldname, value)
	else:
		doc = frappe.get_doc(doctype, name)
		df = doc.meta.get_field(fieldname)
		if df.fieldtype == "Read Only" or df.read_only:
			frappe.throw(_("Can not edit Read Only fields"))
		else:
			doc.set(fieldname, value)

	doc.save()

	return doc.as_dict()

@frappe.whitelist()
def insert(doc=None):
	if isinstance(doc, basestring):
		doc = json.loads(doc)

	if doc.get("parent") and doc.get("parenttype"):
		# inserting a child record
		parent = frappe.get_doc(doc.parenttype, doc.parent)
		parent.append(doc)
		parent.save()
		return parent.as_dict()
	else:
		doc = frappe.get_doc(doc).insert()
		return doc.as_dict()

@frappe.whitelist()
def save(doc):
	if isinstance(doc, basestring):
		doc = json.loads(doc)

	doc = frappe.get_doc(doc).save()
	return doc.as_dict()

@frappe.whitelist()
def rename_doc(doctype, old_name, new_name, merge=False):
	new_name = frappe.rename_doc(doctype, old_name, new_name, merge=merge)
	return new_name

@frappe.whitelist()
def submit(doc):
	if isinstance(doc, basestring):
		doc = json.loads(doc)

	doc = frappe.get_doc(doc)
	doc.submit()

	return doc.as_dict()

@frappe.whitelist()
def cancel(doctype, name):
	wrapper = frappe.get_doc(doctype, name)
	wrapper.cancel()

	return wrapper.as_dict()

@frappe.whitelist()
def delete(doctype, name):
	frappe.delete_doc(doctype, name)

@frappe.whitelist()
def set_default(key, value, parent=None):
	"""set a user default value"""
	frappe.db.set_default(key, value, parent or frappe.session.user)
	frappe.clear_cache(user=frappe.session.user)

@frappe.whitelist()
def make_width_property_setter(doc):
	if isinstance(doc, basestring):
		doc = json.loads(doc)
	if doc["doctype"]=="Property Setter" and doc["property"]=="width":
		frappe.get_doc(doc).insert(ignore_permissions = True)

@frappe.whitelist()
def bulk_update(docs):
	docs = json.loads(docs)
	failed_docs = []
	for doc in docs:
		try:
			ddoc = {key: val for key, val in doc.iteritems() if key not in ['doctype', 'docname']}
			doctype = doc['doctype']
			docname = doc['docname']
			doc = frappe.get_doc(doctype, docname)
			doc.update(ddoc)
			doc.save()
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
	src = src.strip("/").split("/")

	if ".." in src:
		frappe.throw(_("Invalid file path: {0}").format("/".join(src)))

	contentpath = os.path.join(frappe.local.sites_path, *src)
	with open(contentpath, "r") as srcfile:
		code = frappe.utils.cstr(srcfile.read())

	if frappe.local.lang != "en":
		messages = frappe.get_lang_dict("jsfile", contentpath)
		messages = json.dumps(messages)
		code += "\n\n$.extend(frappe._messages, {})".format(messages)
	return code
