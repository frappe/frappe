# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals
import frappe, json
import frappe.utils
import frappe.share
import frappe.defaults
import frappe.desk.form.meta
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
			raise frappe.PermissionError, ("read", doctype, name)

		# add file list
		get_docinfo(doc)

	except Exception:
		frappe.errprint(frappe.utils.get_traceback())
		frappe.msgprint(_('Did not load'))
		raise

	if doc and not name.startswith('_'):
		frappe.get_user().update_recent(doctype, name)

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
	bundle = [frappe.desk.form.meta.get_meta(doctype)]
	for df in bundle[0].fields:
		if df.fieldtype=="Table":
			bundle.append(frappe.desk.form.meta.get_meta(df.options, not frappe.conf.developer_mode))
	return bundle

@frappe.whitelist()
def get_docinfo(doc=None, doctype=None, name=None):
	if not doc:
		doc = frappe.get_doc(doctype, name)
		if not doc.has_permission("read"):
			raise frappe.PermissionError

	frappe.response["docinfo"] = {
		"attachments": get_attachments(doc.doctype, doc.name),
		"comments": get_comments(doc.doctype, doc.name),
		"assignments": get_assignments(doc.doctype, doc.name),
		"permissions": get_doc_permissions(doc),
		"shared": frappe.share.get_users(doc.doctype, doc.name,
			fields=["user", "read", "write", "share", "everyone"])
	}

def get_user_permissions(meta):
	out = {}
	all_user_permissions = frappe.defaults.get_user_permissions()
	for df in meta.get_fields_to_check_permissions(all_user_permissions):
		out[df.options] = list(set(all_user_permissions[df.options]))
	return out

def get_attachments(dt, dn):
	return frappe.get_all("File", fields=["name", "file_name", "file_url"],
		filters = {"attached_to_name": dn, "attached_to_doctype": dt})

def get_comments(dt, dn, limit=100):
	comments = frappe.db.sql("""select name, comment, comment_by, creation,
			reference_doctype, reference_name, comment_type, "Comment" as doctype
		from `tabComment`
		where comment_doctype=%s and comment_docname=%s
		order by creation desc limit %s""",
			(dt, dn, limit), as_dict=1)

	communications = frappe.db.sql("""select name,
			content as comment, sender as comment_by, creation,
			communication_medium as comment_type, subject, delivery_status,
			"Communication" as doctype
		from tabCommunication
		where reference_doctype=%s and reference_name=%s
		order by creation desc limit %s""", (dt, dn, limit),
			as_dict=True)

	for c in communications:
		c.attachments = json.dumps([f.file_url for f in frappe.get_all("File",
			fields=["file_url"],
			filters={"attached_to_doctype": "Communication",
				"attached_to_name": c.name}
			)])

	return comments + communications

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
