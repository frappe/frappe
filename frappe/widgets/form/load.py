# Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals
import frappe, json
import frappe.utils
import frappe.defaults
import frappe.widgets.form.meta
from frappe.permissions import get_doc_permissions
from frappe import _

@frappe.whitelist()
def getdoc(doctype, name, user=None):
	"""
	Loads a doclist for a given document. This method is called directly from the client.
	Requries "doctype", "name" as form variables.
	Will also call the "onload" method on the document.
	"""

	if not (doctype and name):
		raise Exception, 'doctype and name required!'

	if not name:
		name = doctype

	if not frappe.db.exists(doctype, name):
		return []

	try:
		doc = frappe.get_doc(doctype, name)
		run_onload(doc)

		if not doc.has_permission("read"):
			raise frappe.PermissionError, "read"

		# add file list
		get_docinfo(doc)

	except Exception:
		frappe.errprint(frappe.utils.get_traceback())
		frappe.msgprint(_('Did not load'))
		raise

	if doc and not name.startswith('_'):
		frappe.user.update_recent(doctype, name)

	frappe.response.docs.append(doc)

@frappe.whitelist()
def getdoctype(doctype, with_parent=False, cached_timestamp=None):
	"""load doctype"""

	docs = []
	# with parent (called from report builder)
	if with_parent:
		parent_dt = frappe.model.meta.get_parent_dt(doctype)
		if parent_dt:
			docs = get_meta_bundle(parent_dt)
			frappe.response['parent_dt'] = parent_dt

	if not docs:
		docs = get_meta_bundle(doctype)

	frappe.response['user_permissions'] = get_user_permissions(docs[0])

	if cached_timestamp and docs[0].modified==cached_timestamp:
		return "use_cache"

	frappe.response.docs.extend(docs)

def get_meta_bundle(doctype):
	bundle = [frappe.widgets.form.meta.get_meta(doctype)]
	for df in bundle[0].fields:
		if df.fieldtype=="Table":
			bundle.append(frappe.widgets.form.meta.get_meta(df.options))
	return bundle

def get_docinfo(doc):
	frappe.response["docinfo"] = {
		"attachments": get_attachments(doc.doctype, doc.name),
		"comments": get_comments(doc.doctype, doc.name),
		"assignments": get_assignments(doc.doctype, doc.name),
		"permissions": get_doc_permissions(doc)
	}

def get_user_permissions(meta):
	out = {}
	all_user_permissions = frappe.defaults.get_user_permissions()
	for df in meta.get_fields_to_check_permissions(all_user_permissions):
		out[df.options] = all_user_permissions[df.options]
	return out

def get_attachments(dt, dn):
	attachments = []
	for f in frappe.db.sql("""select name, file_name, file_url from
		`tabFile Data` where attached_to_name=%s and attached_to_doctype=%s""",
			(dn, dt), as_dict=True):
		attachments.append({
			'name': f.name,
			'file_url': f.file_url,
			'file_name': f.file_name
		})

	return attachments

def get_comments(dt, dn, limit=100):
	cl = frappe.db.sql("""select name, comment, comment_by, creation, comment_type from `tabComment`
		where comment_doctype=%s and comment_docname=%s
		order by creation asc limit %s""" % ('%s','%s', limit), (dt, dn), as_dict=1)

	return cl

def get_assignments(dt, dn):
	cl = frappe.db.sql("""select owner, description from `tabToDo`
		where reference_type=%(doctype)s and reference_name=%(name)s and status="Open"
		order by modified desc limit 5""", {
			"doctype": dt,
			"name": dn
		}, as_dict=True)

	return cl

@frappe.whitelist()
def get_badge_info(doctypes, filters):
	filters = json.loads(filters)
	doctypes = json.loads(doctypes)
	filters["docstatus"] = ["!=", 2]
	out = {}
	for doctype in doctypes:
		out[doctype] = frappe.db.get_value(doctype, filters, "count(*)")

	return out

def run_onload(doc):
	doc.set("__onload", frappe._dict())
	doc.run_method("onload")
