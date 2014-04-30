# Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals
import frappe, json
import frappe.utils
import frappe.defaults
import frappe.widgets.form.meta
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
		doc.run_method("onload")

		if not doc.has_permission("read"):
			raise frappe.PermissionError, "read"

		# add file list
		get_docinfo(doctype, name)

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

	frappe.response['restrictions'] = get_restrictions(docs[0])

	if cached_timestamp and docs[0].modified==cached_timestamp:
		return "use_cache"

	frappe.response.docs.extend(docs)

def get_meta_bundle(doctype):
	bundle = [frappe.widgets.form.meta.get_meta(doctype)]
	for df in bundle[0].fields:
		if df.fieldtype=="Table":
			bundle.append(frappe.widgets.form.meta.get_meta(df.options))
	return bundle

def get_docinfo(doctype, name):
	frappe.response["docinfo"] = {
		"attachments": add_attachments(doctype, name),
		"comments": add_comments(doctype, name),
		"assignments": add_assignments(doctype, name)
	}

def get_restrictions(meta):
	out = {}
	all_restrictions = frappe.defaults.get_restrictions()
	for df in meta.get_restricted_fields(all_restrictions):
		out[df.options] = all_restrictions[df.options]
	return out

def add_attachments(dt, dn):
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

def add_comments(dt, dn, limit=20):
	cl = frappe.db.sql("""select name, comment, comment_by, creation from `tabComment`
		where comment_doctype=%s and comment_docname=%s
		order by creation desc limit %s""" % ('%s','%s', limit), (dt, dn), as_dict=1)

	return cl

def add_assignments(dt, dn):
	cl = frappe.db.sql_list("""select owner from `tabToDo`
		where reference_type=%(doctype)s and reference_name=%(name)s and status="Open"
		order by modified desc limit 5""", {
			"doctype": dt,
			"name": dn
		})

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
