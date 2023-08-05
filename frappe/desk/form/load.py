# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

import json
from urllib.parse import quote

import frappe
import frappe.defaults
import frappe.desk.form.meta
import frappe.utils
from frappe import _, _dict
from frappe.desk.form.document_follow import is_document_followed
from frappe.model.utils import is_virtual_doctype
from frappe.model.utils.user_settings import get_user_settings
from frappe.permissions import get_doc_permissions
from frappe.utils.data import cstr


@frappe.whitelist()
def getdoc(doctype, name, user=None):
	"""
	Loads a doclist for a given document. This method is called directly from the client.
	Requries "doctype", "name" as form variables.
	Will also call the "onload" method on the document.
	"""

	if not (doctype and name):
		raise Exception("doctype and name required!")

	if not name:
		name = doctype

	if not is_virtual_doctype(doctype) and not frappe.db.exists(doctype, name):
		return []

	doc = frappe.get_doc(doctype, name)
	run_onload(doc)

	if not doc.has_permission("read"):
		frappe.flags.error_message = _("Insufficient Permission for {0}").format(
			frappe.bold(doctype + " " + name)
		)
		raise frappe.PermissionError(("read", doctype, name))

	# ignores system setting (apply_perm_level_on_api_calls) unconditionally to maintain backward compatibility
	doc.apply_fieldlevel_read_permissions()

	# add file list
	doc.add_viewed()
	get_docinfo(doc)

	doc.add_seen()
	set_link_titles(doc)
	if frappe.response.docs is None:
		frappe.local.response = _dict({"docs": []})
	frappe.response.docs.append(doc)


@frappe.whitelist()
def getdoctype(doctype, with_parent=False, cached_timestamp=None):
	"""load doctype"""

	docs = []
	parent_dt = None

	# with parent (called from report builder)
	if with_parent and (parent_dt := frappe.model.meta.get_parent_dt(doctype)):
		docs = get_meta_bundle(parent_dt)
		frappe.response["parent_dt"] = parent_dt

	if not docs:
		docs = get_meta_bundle(doctype)

	frappe.response["user_settings"] = get_user_settings(parent_dt or doctype)

	if cached_timestamp and docs[0].modified == cached_timestamp:
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
	from frappe.share import _get_users as get_docshares

	if not doc:
		doc = frappe.get_doc(doctype, name)
		if not doc.has_permission("read"):
			raise frappe.PermissionError

	all_communications = _get_communications(doc.doctype, doc.name, limit=21)
	automated_messages = [
		msg for msg in all_communications if msg["communication_type"] == "Automated Message"
	]
	communications_except_auto_messages = [
		msg for msg in all_communications if msg["communication_type"] != "Automated Message"
	]

	docinfo = frappe._dict(user_info={})

	add_comments(doc, docinfo)

	docinfo.update(
		{
			"doctype": doc.doctype,
			"name": doc.name,
			"attachments": get_attachments(doc.doctype, doc.name),
			"communications": communications_except_auto_messages,
			"automated_messages": automated_messages,
			"total_comments": len(json.loads(doc.get("_comments") or "[]")),
			"versions": get_versions(doc),
			"assignments": get_assignments(doc.doctype, doc.name),
			"permissions": get_doc_permissions(doc),
			"shared": get_docshares(doc),
			"views": get_view_logs(doc.doctype, doc.name),
			"energy_point_logs": get_point_logs(doc.doctype, doc.name),
			"additional_timeline_content": get_additional_timeline_content(doc.doctype, doc.name),
			"milestones": get_milestones(doc.doctype, doc.name),
			"is_document_followed": is_document_followed(doc.doctype, doc.name, frappe.session.user),
			"tags": get_tags(doc.doctype, doc.name),
			"document_email": get_document_email(doc.doctype, doc.name),
		}
	)

	update_user_info(docinfo)

	frappe.response["docinfo"] = docinfo


def add_comments(doc, docinfo):
	# divide comments into separate lists
	docinfo.comments = []
	docinfo.shared = []
	docinfo.assignment_logs = []
	docinfo.attachment_logs = []
	docinfo.info_logs = []
	docinfo.like_logs = []
	docinfo.workflow_logs = []

	comments = frappe.get_all(
		"Comment",
		fields=["name", "creation", "content", "owner", "comment_type"],
		filters={"reference_doctype": doc.doctype, "reference_name": doc.name},
	)

	for c in comments:
		if c.comment_type == "Comment":
			c.content = frappe.utils.markdown(c.content)
			docinfo.comments.append(c)

		elif c.comment_type in ("Shared", "Unshared"):
			docinfo.shared.append(c)

		elif c.comment_type in ("Assignment Completed", "Assigned"):
			docinfo.assignment_logs.append(c)

		elif c.comment_type in ("Attachment", "Attachment Removed"):
			docinfo.attachment_logs.append(c)

		elif c.comment_type in ("Info", "Edit", "Label"):
			docinfo.info_logs.append(c)

		elif c.comment_type == "Like":
			docinfo.like_logs.append(c)

		elif c.comment_type == "Workflow":
			docinfo.workflow_logs.append(c)

		frappe.utils.add_user_info(c.owner, docinfo.user_info)

	return comments


def get_milestones(doctype, name):
	return frappe.get_all(
		"Milestone",
		fields=["creation", "owner", "track_field", "value"],
		filters=dict(reference_type=doctype, reference_name=name),
	)


def get_attachments(dt, dn):
	return frappe.get_all(
		"File",
		fields=["name", "file_name", "file_url", "is_private"],
		filters={"attached_to_name": dn, "attached_to_doctype": dt},
	)


def get_versions(doc):
	return frappe.get_all(
		"Version",
		filters=dict(ref_doctype=doc.doctype, docname=doc.name),
		fields=["name", "owner", "creation", "data"],
		limit=10,
		order_by="creation desc",
	)


@frappe.whitelist()
def get_communications(doctype, name, start=0, limit=20):
	from frappe.utils import cint

	doc = frappe.get_doc(doctype, name)
	if not doc.has_permission("read"):
		raise frappe.PermissionError

	return _get_communications(doctype, name, cint(start), cint(limit))


def get_comments(
	doctype: str, name: str, comment_type: str | list[str] = "Comment"
) -> list[frappe._dict]:
	if isinstance(comment_type, list):
		comment_types = comment_type

	elif comment_type == "share":
		comment_types = ["Shared", "Unshared"]

	elif comment_type == "assignment":
		comment_types = ["Assignment Completed", "Assigned"]

	elif comment_type == "attachment":
		comment_types = ["Attachment", "Attachment Removed"]

	else:
		comment_types = [comment_type]

	comments = frappe.get_all(
		"Comment",
		fields=["name", "creation", "content", "owner", "comment_type"],
		filters={
			"reference_doctype": doctype,
			"reference_name": name,
			"comment_type": ["in", comment_types],
		},
	)

	# convert to markdown (legacy ?)
	for c in comments:
		if c.comment_type == "Comment":
			c.content = frappe.utils.markdown(c.content)

	return comments


def get_point_logs(doctype, docname):
	return frappe.get_all(
		"Energy Point Log",
		filters={"reference_doctype": doctype, "reference_name": docname, "type": ["!=", "Review"]},
		fields=["*"],
	)


def _get_communications(doctype, name, start=0, limit=20):
	communications = get_communication_data(doctype, name, start, limit)
	for c in communications:
		if c.communication_type == "Communication":
			c.attachments = json.dumps(
				frappe.get_all(
					"File",
					fields=["file_url", "is_private"],
					filters={"attached_to_doctype": "Communication", "attached_to_name": c.name},
				)
			)

	return communications


def get_communication_data(
	doctype, name, start=0, limit=20, after=None, fields=None, group_by=None, as_dict=True
):
	"""Returns list of communications for a given document"""
	if not fields:
		fields = """
			C.name, C.communication_type, C.communication_medium,
			C.comment_type, C.communication_date, C.content,
			C.sender, C.sender_full_name, C.cc, C.bcc,
			C.creation AS creation, C.subject, C.delivery_status,
			C._liked_by, C.reference_doctype, C.reference_name,
			C.read_by_recipient, C.rating, C.recipients
		"""

	conditions = ""
	if after:
		# find after a particular date
		conditions += """
			AND C.creation > {}
		""".format(
			after
		)

	if doctype == "User":
		conditions += """
			AND NOT (C.reference_doctype='User' AND C.communication_type='Communication')
		"""

	# communications linked to reference_doctype
	part1 = """
		SELECT {fields}
		FROM `tabCommunication` as C
		WHERE C.communication_type IN ('Communication', 'Feedback', 'Automated Message')
		AND (C.reference_doctype = %(doctype)s AND C.reference_name = %(name)s)
		{conditions}
	""".format(
		fields=fields, conditions=conditions
	)

	# communications linked in Timeline Links
	part2 = """
		SELECT {fields}
		FROM `tabCommunication` as C
		INNER JOIN `tabCommunication Link` ON C.name=`tabCommunication Link`.parent
		WHERE C.communication_type IN ('Communication', 'Feedback', 'Automated Message')
		AND `tabCommunication Link`.link_doctype = %(doctype)s AND `tabCommunication Link`.link_name = %(name)s
		{conditions}
	""".format(
		fields=fields, conditions=conditions
	)

	communications = frappe.db.sql(
		"""
		SELECT *
		FROM (({part1}) UNION ({part2})) AS combined
		{group_by}
		ORDER BY creation DESC
		LIMIT %(limit)s
		OFFSET %(start)s
	""".format(
			part1=part1, part2=part2, group_by=(group_by or "")
		),
		dict(doctype=doctype, name=name, start=frappe.utils.cint(start), limit=limit),
		as_dict=as_dict,
	)

	return communications


def get_assignments(dt, dn):
	return frappe.get_all(
		"ToDo",
		fields=["name", "allocated_to as owner", "description", "status"],
		filters={
			"reference_type": dt,
			"reference_name": dn,
			"status": ("!=", "Cancelled"),
			"allocated_to": ("is", "set"),
		},
	)


def run_onload(doc):
	doc.set("__onload", frappe._dict())
	doc.run_method("onload")


def get_view_logs(doctype, docname):
	"""get and return the latest view logs if available"""
	logs = []
	if hasattr(frappe.get_meta(doctype), "track_views") and frappe.get_meta(doctype).track_views:
		view_logs = frappe.get_all(
			"View Log",
			filters={
				"reference_doctype": doctype,
				"reference_name": docname,
			},
			fields=["name", "creation", "owner"],
			order_by="creation desc",
		)

		if view_logs:
			logs = view_logs
	return logs


def get_tags(doctype, name):
	tags = [
		tag.tag
		for tag in frappe.get_all(
			"Tag Link", filters={"document_type": doctype, "document_name": name}, fields=["tag"]
		)
	]

	return ",".join(tags)


def get_document_email(doctype, name):
	email = get_automatic_email_link()
	if not email:
		return None

	email = email.split("@")
	return f"{email[0]}+{quote(doctype)}={quote(cstr(name))}@{email[1]}"


def get_automatic_email_link():
	return frappe.db.get_value(
		"Email Account", {"enable_incoming": 1, "enable_automatic_linking": 1}, "email_id"
	)


def get_additional_timeline_content(doctype, docname):
	contents = []
	hooks = frappe.get_hooks().get("additional_timeline_content", {})
	methods_for_all_doctype = hooks.get("*", [])
	methods_for_current_doctype = hooks.get(doctype, [])

	for method in methods_for_all_doctype + methods_for_current_doctype:
		contents.extend(frappe.get_attr(method)(doctype, docname) or [])

	return contents


def set_link_titles(doc):
	link_titles = {}
	link_titles.update(get_title_values_for_link_and_dynamic_link_fields(doc))
	link_titles.update(get_title_values_for_table_and_multiselect_fields(doc))

	send_link_titles(link_titles)


def get_title_values_for_link_and_dynamic_link_fields(doc, link_fields=None):
	link_titles = {}

	if not link_fields:
		meta = frappe.get_meta(doc.doctype)
		link_fields = meta.get_link_fields() + meta.get_dynamic_link_fields()

	for field in link_fields:
		if not doc.get(field.fieldname):
			continue

		doctype = field.options if field.fieldtype == "Link" else doc.get(field.options)

		meta = frappe.get_meta(doctype)
		if not meta or not (meta.title_field and meta.show_title_field_in_link):
			continue

		link_title = frappe.db.get_value(
			doctype, doc.get(field.fieldname), meta.title_field, cache=True, order_by=None
		)
		link_titles.update({doctype + "::" + doc.get(field.fieldname): link_title})

	return link_titles


def get_title_values_for_table_and_multiselect_fields(doc, table_fields=None):
	link_titles = {}

	if not table_fields:
		meta = frappe.get_meta(doc.doctype)
		table_fields = meta.get_table_fields()

	for field in table_fields:
		if not doc.get(field.fieldname):
			continue

		for value in doc.get(field.fieldname):
			link_titles.update(get_title_values_for_link_and_dynamic_link_fields(value))

	return link_titles


def send_link_titles(link_titles):
	"""Append link titles dict in `frappe.local.response`."""
	if "_link_titles" not in frappe.local.response:
		frappe.local.response["_link_titles"] = {}

	frappe.local.response["_link_titles"].update(link_titles)


def update_user_info(docinfo):
	for d in docinfo.communications:
		frappe.utils.add_user_info(d.sender, docinfo.user_info)

	for d in docinfo.shared:
		frappe.utils.add_user_info(d.user, docinfo.user_info)

	for d in docinfo.assignments:
		frappe.utils.add_user_info(d.owner, docinfo.user_info)

	for d in docinfo.views:
		frappe.utils.add_user_info(d.owner, docinfo.user_info)


@frappe.whitelist()
def get_user_info_for_viewers(users):
	user_info = {}
	for user in json.loads(users):
		frappe.utils.add_user_info(user, user_info)

	return user_info
