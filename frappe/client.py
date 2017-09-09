# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals
import frappe
from frappe import _
import frappe.model
import frappe.utils
import json, os

from six import iteritems, string_types, integer_types

'''
Handle RESTful requests that are mapped to the `/api/resource` route.

Requests via FrappeClient are also handled here.
'''

@frappe.whitelist()
def get_list(doctype, fields=None, filters=None, order_by=None,
	limit_start=None, limit_page_length=20):
	'''Returns a list of records by filters, fields, ordering and limit

	:param doctype: DocType of the data to be queried
	:param fields: fields to be returned. Default is `name`
	:param filters: filter list by this dict
	:param order_by: Order by this fieldname
	:param limit_start: Start at this index
	:param limit_page_length: Number of records to be returned (default 20)'''
	return frappe.get_list(doctype, fields=fields, filters=filters, order_by=order_by,
		limit_start=limit_start, limit_page_length=limit_page_length, ignore_permissions=False)

@frappe.whitelist()
def get(doctype, name=None, filters=None):
	'''Returns a document by name or filters

	:param doctype: DocType of the document to be returned
	:param name: return document of this `name`
	:param filters: If name is not set, filter by these values and return the first match'''
	if filters and not name:
		name = frappe.db.get_value(doctype, json.loads(filters))
		if not name:
			frappe.throw(_("No document found for given filters"))

	doc = frappe.get_doc(doctype, name)
	if not doc.has_permission("read"):
		raise frappe.PermissionError

	return frappe.get_doc(doctype, name).as_dict()

@frappe.whitelist()
def get_value(doctype, fieldname, filters=None, as_dict=True, debug=False):
	'''Returns a value form a document

	:param doctype: DocType to be queried
	:param fieldname: Field to be returned (default `name`)
	:param filters: dict or string for identifying the record'''

	if not frappe.has_permission(doctype):
		frappe.throw(_("Not permitted"), frappe.PermissionError)

	try:
		filters = json.loads(filters)

		if isinstance(filters, (integer_types, float)):
			filters = frappe.as_unicode(filters)

	except (TypeError, ValueError):
		# filters are not passesd, not json
		pass

	try:
		fieldname = json.loads(fieldname)
	except (TypeError, ValueError):
		# name passed, not json
		pass

	# check whether the used filters were really parseable and usable
	# and did not just result in an empty string or dict
	if not filters:
		filters = None

	return frappe.db.get_value(doctype, filters, fieldname, as_dict=as_dict, debug=debug)

@frappe.whitelist()
def set_value(doctype, name, fieldname, value=None):
	'''Set a value using get_doc, group of values

	:param doctype: DocType of the document
	:param name: name of the document
	:param fieldname: fieldname string or JSON / dict with key value pair
	:param value: value if fieldname is JSON / dict'''

	if fieldname!="idx" and fieldname in frappe.model.default_fields:
		frappe.throw(_("Cannot edit standard fields"))

	if not value:
		values = fieldname
		if isinstance(fieldname, string_types):
			try:
				values = json.loads(fieldname)
			except ValueError:
				values = {fieldname: ''}
	else:
		values = {fieldname: value}

	doc = frappe.db.get_value(doctype, name, ["parenttype", "parent"], as_dict=True)
	if doc and doc.parent and doc.parenttype:
		doc = frappe.get_doc(doc.parenttype, doc.parent)
		child = doc.getone({"doctype": doctype, "name": name})
		child.update(values)
	else:
		doc = frappe.get_doc(doctype, name)
		doc.update(values)

	doc.save()

	return doc.as_dict()

@frappe.whitelist()
def insert(doc=None):
	'''Insert a document

	:param doc: JSON or dict object to be inserted'''
	if isinstance(doc, string_types):
		doc = json.loads(doc)

	if doc.get("parent") and doc.get("parenttype"):
		# inserting a child record
		parent = frappe.get_doc(doc.get("parenttype"), doc.get("parent"))
		parent.append(doc.get("parentfield"), doc)
		parent.save()
		return parent.as_dict()
	else:
		doc = frappe.get_doc(doc).insert()
		return doc.as_dict()

@frappe.whitelist()
def insert_many(docs=None):
	'''Insert multiple documents

	:param docs: JSON or list of dict objects to be inserted in one request'''
	if isinstance(docs, string_types):
		docs = json.loads(docs)

	out = []

	if len(docs) > 200:
		frappe.throw(_('Only 200 inserts allowed in one request'))

	for doc in docs:
		if doc.get("parent") and doc.get("parenttype"):
			# inserting a child record
			parent = frappe.get_doc(doc.get("parenttype"), doc.get("parent"))
			parent.append(doc.get("parentfield"), doc)
			parent.save()
			out.append(parent.name)
		else:
			doc = frappe.get_doc(doc).insert()
			out.append(doc.name)

	return out

@frappe.whitelist()
def save(doc):
	'''Update (save) an existing document

	:param doc: JSON or dict object with the properties of the document to be updated'''
	if isinstance(doc, string_types):
		doc = json.loads(doc)

	doc = frappe.get_doc(doc).save()
	return doc.as_dict()

@frappe.whitelist()
def rename_doc(doctype, old_name, new_name, merge=False):
	'''Rename document

	:param doctype: DocType of the document to be renamed
	:param old_name: Current `name` of the document to be renamed
	:param new_name: New `name` to be set'''
	new_name = frappe.rename_doc(doctype, old_name, new_name, merge=merge)
	return new_name

@frappe.whitelist()
def submit(doc):
	'''Submit a document

	:param doc: JSON or dict object to be submitted remotely'''
	if isinstance(doc, string_types):
		doc = json.loads(doc)

	doc = frappe.get_doc(doc)
	doc.submit()

	return doc.as_dict()

@frappe.whitelist()
def cancel(doctype, name):
	'''Cancel a document

	:param doctype: DocType of the document to be cancelled
	:param name: name of the document to be cancelled'''
	wrapper = frappe.get_doc(doctype, name)
	wrapper.cancel()

	return wrapper.as_dict()

@frappe.whitelist()
def delete(doctype, name):
	'''Delete a remote document

	:param doctype: DocType of the document to be deleted
	:param name: name of the document to be deleted'''
	frappe.delete_doc(doctype, name, ignore_missing=False)

@frappe.whitelist()
def set_default(key, value, parent=None):
	"""set a user default value"""
	frappe.db.set_default(key, value, parent or frappe.session.user)
	frappe.clear_cache(user=frappe.session.user)

@frappe.whitelist()
def make_width_property_setter(doc):
	'''Set width Property Setter

	:param doc: Property Setter document with `width` property'''
	if isinstance(doc, string_types):
		doc = json.loads(doc)
	if doc["doctype"]=="Property Setter" and doc["property"]=="width":
		frappe.get_doc(doc).insert(ignore_permissions = True)

@frappe.whitelist()
def bulk_update(docs):
	'''Bulk update documents

	:param docs: JSON list of documents to be updated remotely. Each document must have `docname` property'''
	docs = json.loads(docs)
	failed_docs = []
	for doc in docs:
		try:
			ddoc = {key: val for key, val in iteritems(doc) if key not in ['doctype', 'docname']}
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
	'''Returns a JSON with data whether the document has the requested permission

	:param doctype: DocType of the document to be checked
	:param docname: `name` of the document to be checked
	:param perm_type: one of `read`, `write`, `create`, `submit`, `cancel`, `report`. Default is `read`'''
	# perm_type can be one of read, write, create, submit, cancel, report
	return {"has_permission": frappe.has_permission(doctype, perm_type.lower(), docname)}

@frappe.whitelist()
def get_password(doctype, name, fieldname):
	'''Return a password type property. Only applicable for System Managers

	:param doctype: DocType of the document that holds the password
	:param name: `name` of the document that holds the password
	:param fieldname: `fieldname` of the password property
	'''
	frappe.only_for("System Manager")
	return frappe.get_doc(doctype, name).get_password(fieldname)


@frappe.whitelist()
def get_js(items):
	'''Load JS code files.  Will also append translations
	and extend `frappe._messages`

	:param items: JSON list of paths of the js files to be loaded.'''
	items = json.loads(items)
	out = []
	for src in items:
		src = src.strip("/").split("/")

		if ".." in src or src[0] != "assets":
			frappe.throw(_("Invalid file path: {0}").format("/".join(src)))

		contentpath = os.path.join(frappe.local.sites_path, *src)
		with open(contentpath, "r") as srcfile:
			code = frappe.utils.cstr(srcfile.read())

		if frappe.local.lang != "en":
			messages = frappe.get_lang_dict("jsfile", contentpath)
			messages = json.dumps(messages)
			code += "\n\n$.extend(frappe._messages, {})".format(messages)

		out.append(code)

	return out

@frappe.whitelist(allow_guest=True)
def get_time_zone():
	'''Returns default time zone'''
	return {"time_zone": frappe.defaults.get_defaults().get("time_zone")}
