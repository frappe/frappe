# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

import json
import typing
from urllib.parse import quote_plus

import frappe
import frappe.defaults
import frappe.desk.form.meta
import frappe.utils
from frappe import _, _dict
from frappe.desk.form.document_follow import is_document_followed
from frappe.model.utils.user_settings import get_user_settings
from frappe.permissions import check_doctype_permission, get_doc_permissions, has_permission
from frappe.utils.data import cstr

if typing.TYPE_CHECKING:
	from frappe.model.document import Document


@frappe.whitelist()
def getdoc(doctype, name):
	"""
	Loads a doclist for a given document. This method is called directly from the client.
	Requries "doctype", "name" as form variables.
	Will also call the "onload" method on the document.
	"""

	if not (doctype and name):
		raise Exception("doctype and name required!")

	try:
		doc = frappe.get_doc(doctype, name)
	except frappe.DoesNotExistError:
		check_doctype_permission(doctype)
		frappe.clear_last_message()
		return []

	doc.check_permission("read")

	# Replace cache if stale one exists
	# PERF: This should be eventually removed completely when we are sure about caching correctness
	if (key := frappe.can_cache_doc((doctype, name))) and frappe.cache.exists(key):
		frappe._set_document_in_cache(key, doc)

	run_onload(doc)
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
	bundle.extend(
		frappe.desk.form.meta.get_meta(df.options)
		for df in bundle[0].fields
		if df.fieldtype in frappe.model.table_fields
	)
	return bundle


@frappe.whitelist()
def get_docinfo(doc=None, doctype=None, name=None):
	from frappe.share import _get_users as get_docshares

	if not doc:
		doc = frappe.get_lazy_doc(doctype, name)
		doc.check_permission("read")

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
			"versions": get_versions(doc),
			"assignments": get_assignments(doc.doctype, doc.name),
			"permissions": get_doc_permissions(doc),
			"shared": get_docshares(doc),
			"views": get_view_logs(doc),
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
		fields=["name", "creation", "content", "owner", "comment_type", "published"],
		filters={"reference_doctype": doc.doctype, "reference_name": doc.name},
	)

	for c in comments:
		match c.comment_type:
			case "Comment":
				c.content = frappe.utils.markdown(c.content)
				docinfo.comments.append(c)
			case "Shared" | "Unshared":
				docinfo.shared.append(c)
			case "Assignment Completed" | "Assigned":
				docinfo.assignment_logs.append(c)
			case "Attachment" | "Attachment Removed":
				docinfo.attachment_logs.append(c)
			case "Info" | "Edit" | "Label":
				docinfo.info_logs.append(c)
			case "Like":
				docinfo.like_logs.append(c)
			case "Workflow":
				docinfo.workflow_logs.append(c)

	return comments


def get_milestones(doctype, name):
	return frappe.get_all(
		"Milestone",
		fields=["creation", "owner", "track_field", "value"],
		filters=dict(reference_type=doctype, reference_name=str(name)),
	)


def get_attachments(dt, dn):
	return frappe.get_all(
		"File",
		fields=["name", "file_name", "file_url", "is_private"],
		filters={"attached_to_name": str(dn), "attached_to_doctype": dt},
	)


def get_versions(doc: "Document") -> list[dict]:
	if not doc.meta.track_changes:
		return []
	return frappe.get_all(
		"Version",
		filters=dict(ref_doctype=doc.doctype, docname=str(doc.name)),
		fields=["name", "owner", "creation", "data"],
		limit=10,
		order_by="creation desc",
	)


@frappe.whitelist()
def get_communications(doctype, name, start=0, limit=20):
	from frappe.utils import cint

	doc = frappe.get_lazy_doc(doctype, name)
	doc.check_permission("read")

	return _get_communications(doctype, name, cint(start), cint(limit))


def get_comments(doctype: str, name: str, comment_type: str | list[str] = "Comment") -> list[frappe._dict]:
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


def _get_communications(doctype, name, start=0, limit=20):
	communications = get_communication_data(doctype, name, start, limit)
	for c in communications:
		if c.communication_type in ("Communication", "Automated Message"):
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
	"""Return list of communications for a given document."""
	if not fields:
		fields = """
			C.name, C.communication_type, C.communication_medium,
			C.communication_date, C.content,
			C.sender, C.sender_full_name, C.cc, C.bcc,
			C.creation AS creation, C.subject, C.delivery_status,
			C._liked_by, C.reference_doctype, C.reference_name,
			C.read_by_recipient, C.recipients
		"""

	conditions = ""
	if after:
		# find after a particular date
		conditions += f"""
			AND C.communication_date > {after}
		"""

	if doctype == "User":
		conditions += """
			AND NOT (C.reference_doctype='User' AND C.communication_type='Communication')
		"""

	# communications linked to reference_doctype
	part1 = f"""
		SELECT {fields}
		FROM `tabCommunication` as C
		WHERE C.communication_type IN ('Communication', 'Automated Message')
		AND (C.reference_doctype = %(doctype)s AND C.reference_name = %(name)s)
		{conditions}
	"""

	# communications linked in Timeline Links
	part2 = f"""
		SELECT {fields}
		FROM `tabCommunication` as C
		INNER JOIN `tabCommunication Link` ON C.name=`tabCommunication Link`.parent
		WHERE C.communication_type IN ('Communication', 'Automated Message')
		AND `tabCommunication Link`.link_doctype = %(doctype)s AND `tabCommunication Link`.link_name = %(name)s
		{conditions}
	"""

	sqlite_query = f"""
		SELECT * FROM (
			SELECT * FROM ({part1})
			UNION ALL
			SELECT * FROM ({part2})
		) AS combined
		{group_by or ""}
		ORDER BY communication_date DESC
		LIMIT %(limit)s
		OFFSET %(start)s"""

	query = f"""
		SELECT *
		FROM (({part1}) UNION ({part2})) AS combined
		{group_by or ""}
		ORDER BY communication_date DESC
		LIMIT %(limit)s
		OFFSET %(start)s
		"""

	return frappe.db.multisql(
		{
			"sqlite": sqlite_query,
			"postgres": query,
			"mariadb": query,
		},
		dict(
			doctype=doctype,
			name=str(name),
			start=frappe.utils.cint(start),
			limit=limit,
		),
		as_dict=as_dict,
	)


def get_assignments(dt, dn):
	return frappe.get_all(
		"ToDo",
		fields=["name", "allocated_to as owner", "description", "status"],
		filters={
			"reference_type": dt,
			"reference_name": str(dn),
			"status": ("not in", ("Cancelled", "Closed")),
			"allocated_to": ("is", "set"),
		},
	)


def run_onload(doc):
	doc.set("__onload", frappe._dict())
	doc.run_method("onload")


def get_view_logs(doc: "Document") -> list[dict]:
	"""get and return the latest view logs if available"""
	if not doc.meta.track_views:
		return []

	return frappe.get_all(
		"View Log",
		filters={
			"reference_doctype": doc.doctype,
			"reference_name": str(doc.name),
		},
		fields=["name", "creation", "owner"],
		order_by="creation desc",
	)


def get_tags(doctype: str, name: str) -> str:
	from frappe.desk.doctype.tag_link.tag_link import has_tags

	if not has_tags(doctype):
		return ""

	tags = frappe.get_all(
		"Tag Link",
		filters={"document_type": doctype, "document_name": str(name)},
		fields=["tag"],
		pluck="tag",
	)

	return ",".join(tags)


def get_document_email(doctype, name):
	from frappe.email.doctype.email_account.email_account import get_automatic_email_link

	email = get_automatic_email_link()
	if not email:
		return None

	email = email.split("@")
	return f"{email[0]}+{quote_plus(doctype)}={quote_plus(cstr(name))}@{email[1]}"


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
		if not (doc_fieldvalue := getattr(doc, field.fieldname, None)):
			continue

		doctype = field.options if field.fieldtype == "Link" else doc.get(field.options)

		meta = frappe.get_meta(doctype) if doctype else None
		if not meta or not meta.title_field or not meta.show_title_field_in_link:
			continue

		link_title = frappe.db.get_value(doctype, doc_fieldvalue, meta.title_field, cache=True, order_by=None)
		link_titles.update({doctype + "::" + doc_fieldvalue: link_title or doc_fieldvalue})

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
	users = set()

	users.update(d.sender for d in docinfo.communications)
	users.update(d.user for d in docinfo.shared)
	users.update(d.owner for d in docinfo.assignments)
	users.update(d.owner for d in docinfo.views)
	users.update(d.owner for d in docinfo.workflow_logs)
	users.update(d.owner for d in docinfo.like_logs)
	users.update(d.owner for d in docinfo.info_logs)
	users.update(d.owner for d in docinfo.attachment_logs)
	users.update(d.owner for d in docinfo.assignment_logs)
	users.update(d.owner for d in docinfo.comments)

	frappe.utils.add_user_info(users, docinfo.user_info)


@frappe.whitelist()
def get_user_info_for_viewers(users):
	user_info = {}
	for user in json.loads(users):
		frappe.utils.add_user_info(user, user_info)

	return user_info
