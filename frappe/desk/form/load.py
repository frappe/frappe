# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals
import frappe, json
import frappe.utils
import frappe.share
import frappe.defaults
import frappe.desk.form.meta
from frappe.model.utils.user_settings import get_user_settings
from frappe.permissions import get_doc_permissions
from frappe.desk.form.document_follow import is_document_followed
from frappe import _
from six.moves.urllib.parse import quote

@frappe.whitelist()
def getdoc(doctype, name, user=None):
	"""
	Loads a doclist for a given document. This method is called directly from the client.
	Requries "doctype", "name" as form variables.
	Will also call the "onload" method on the document.
	"""

	if not (doctype and name):
		raise Exception('doctype and name required!')

	if not name:
		name = doctype

	if not frappe.db.exists(doctype, name):
		return []

	try:
		doc = frappe.get_doc(doctype, name)
		run_onload(doc)

		if not doc.has_permission("read"):
			frappe.flags.error_message = _('Insufficient Permission for {0}').format(frappe.bold(doctype + ' ' + name))
			raise frappe.PermissionError(("read", doctype, name))

		doc.apply_fieldlevel_read_permissions()

		# add file list
		doc.add_viewed()
		get_docinfo(doc)

	except Exception:
		frappe.errprint(frappe.utils.get_traceback())
		raise

	doc.add_seen()

	frappe.response.docs.append(doc)

@frappe.whitelist()
def getdoctype(doctype, with_parent=False, cached_timestamp=None):
	"""load doctype"""

	docs = []
	parent_dt = None

	# with parent (called from report builder)
	if with_parent:
		parent_dt = frappe.model.meta.get_parent_dt(doctype)
		if parent_dt:
			docs = get_meta_bundle(parent_dt)
			frappe.response['parent_dt'] = parent_dt

	if not docs:
		docs = get_meta_bundle(doctype)

	frappe.response['user_settings'] = get_user_settings(parent_dt or doctype)

	if cached_timestamp and docs[0].modified==cached_timestamp:
		return "use_cache"

	frappe.response.docs.extend(docs)

def get_meta_bundle(doctype):
	bundle = [frappe.desk.form.meta.get_meta(doctype)]
	for df in bundle[0].fields:
		if df.fieldtype in frappe.model.table_fields:
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
		"communications": _get_communications(doc.doctype, doc.name),
		'comments': get_comments(doc.doctype, doc.name),
		'total_comments': len(json.loads(doc.get('_comments') or '[]')),
		'versions': get_versions(doc),
		"assignments": get_assignments(doc.doctype, doc.name),
		"permissions": get_doc_permissions(doc),
		"shared": frappe.share.get_users(doc.doctype, doc.name),
		"views": get_view_logs(doc.doctype, doc.name),
		"energy_point_logs": get_point_logs(doc.doctype, doc.name),
		"milestones": get_milestones(doc.doctype, doc.name),
		"is_document_followed": is_document_followed(doc.doctype, doc.name, frappe.session.user),
		"tags": get_tags(doc.doctype, doc.name),
		"document_email": get_document_email(doc.doctype, doc.name)
	}

def get_milestones(doctype, name):
	return frappe.db.get_all('Milestone', fields = ['creation', 'owner', 'track_field', 'value'],
		filters=dict(reference_type=doctype, reference_name=name))

def get_attachments(dt, dn):
	return frappe.get_all("File", fields=["name", "file_name", "file_url", "is_private"],
		filters = {"attached_to_name": dn, "attached_to_doctype": dt})

def get_versions(doc):
	return frappe.get_all('Version', filters=dict(ref_doctype=doc.doctype, docname=doc.name),
		fields=['name', 'owner', 'creation', 'data'], limit=10, order_by='creation desc')

@frappe.whitelist()
def get_communications(doctype, name, start=0, limit=20):
	doc = frappe.get_doc(doctype, name)
	if not doc.has_permission("read"):
		raise frappe.PermissionError

	return _get_communications(doctype, name, start, limit)


def get_comments(doctype, name):
	comments = frappe.get_all('Comment', fields = ['*'], filters = dict(
		reference_doctype = doctype,
		reference_name = name
	))

	# convert to markdown (legacy ?)
	for c in comments:
		if c.comment_type == 'Comment':
			c.content = frappe.utils.markdown(c.content)

	return comments

def get_point_logs(doctype, docname):
	return frappe.db.get_all('Energy Point Log', filters={
		'reference_doctype': doctype,
		'reference_name': docname,
		'type': ['!=', 'Review']
	}, fields=['*'])

def _get_communications(doctype, name, start=0, limit=20):
	communications = get_communication_data(doctype, name, start, limit)
	for c in communications:
		if c.communication_type=="Communication":
			c.attachments = json.dumps(frappe.get_all("File",
				fields=["file_url", "is_private"],
				filters={"attached_to_doctype": "Communication",
					"attached_to_name": c.name}
				))

	return communications

def get_communication_data(doctype, name, start=0, limit=20, after=None, fields=None,
	group_by=None, as_dict=True):
	'''Returns list of communications for a given document'''
	if not fields:
		fields = '''
			C.name, C.communication_type, C.communication_medium,
			C.comment_type, C.communication_date, C.content,
			C.sender, C.sender_full_name, C.cc, C.bcc,
			C.creation AS creation, C.subject, C.delivery_status,
			C._liked_by, C.reference_doctype, C.reference_name,
			C.read_by_recipient, C.rating
		'''

	conditions = ''
	if after:
		# find after a particular date
		conditions += '''
			AND C.creation > {0}
		'''.format(after)

	if doctype=='User':
		conditions += '''
			AND NOT (C.reference_doctype='User' AND C.communication_type='Communication')
		'''

	# communications linked to reference_doctype
	part1 = '''
		SELECT {fields}
		FROM `tabCommunication` as C
		WHERE C.communication_type IN ('Communication', 'Feedback')
		AND (C.reference_doctype = %(doctype)s AND C.reference_name = %(name)s)
		{conditions}
	'''.format(fields=fields, conditions=conditions)

	# communications linked in Timeline Links
	part2 = '''
		SELECT {fields}
		FROM `tabCommunication` as C
		INNER JOIN `tabCommunication Link` ON C.name=`tabCommunication Link`.parent
		WHERE C.communication_type IN ('Communication', 'Feedback')
		AND `tabCommunication Link`.link_doctype = %(doctype)s AND `tabCommunication Link`.link_name = %(name)s
		{conditions}
	'''.format(fields=fields, conditions=conditions)

	communications = frappe.db.sql('''
		SELECT *
		FROM (({part1}) UNION ({part2})) AS combined
		{group_by}
		ORDER BY creation DESC
		LIMIT %(limit)s
		OFFSET %(start)s
	'''.format(part1=part1, part2=part2, group_by=(group_by or '')), dict(
		doctype=doctype,
		name=name,
		start=frappe.utils.cint(start),
		limit=limit
	), as_dict=as_dict)

	return communications

def get_assignments(dt, dn):
	cl = frappe.get_all("ToDo",
			fields=['name', 'owner', 'description', 'status'],
			limit= 5,
			filters={
				'reference_type': dt,
				'reference_name': dn,
				'status': ('!=', 'Cancelled'),
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

def run_onload(doc):
	doc.set("__onload", frappe._dict())
	doc.run_method("onload")

def get_view_logs(doctype, docname):
	""" get and return the latest view logs if available """
	logs = []
	if hasattr(frappe.get_meta(doctype), 'track_views') and frappe.get_meta(doctype).track_views:
		view_logs = frappe.get_all("View Log", filters={
			"reference_doctype": doctype,
			"reference_name": docname,
		}, fields=["name", "creation", "owner"], order_by="creation desc")

		if view_logs:
			logs = view_logs
	return logs

def get_tags(doctype, name):
	tags = [tag.tag for tag in frappe.get_all("Tag Link", filters={
			"document_type": doctype,
			"document_name": name
		}, fields=["tag"])]

	return ",".join(tags)

def get_document_email(doctype, name):
	email = get_automatic_email_link()
	if not email:
		return None

	email = email.split("@")
	return "{0}+{1}+{2}@{3}".format(email[0], quote(doctype), quote(name), email[1])

def get_automatic_email_link():
	return frappe.db.get_value("Email Account", {"enable_incoming": 1, "enable_automatic_linking": 1}, "email_id")
