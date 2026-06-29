# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

import json
import re

import frappe
import frappe.utils
from frappe import _
from frappe.desk.form.load import _get_communications, add_comments, get_versions, get_view_logs
from frappe.model.document import Document

# Non-email sources load in full; emails are paged newest-first as the user scrolls up.
EMAIL_PAGE_SIZE = 20


@frappe.whitelist()
def get_activity_timeline(doctype: str, name: str | int) -> dict:
	doc = frappe.get_lazy_doc(doctype, name, check_permission=True)
	user_info: dict = {}  # cache to avoid repeat DB calls for the same user

	emails, has_more_emails = get_email_activities(doc, user_info)
	activities = [
		*get_creation_activity(doc, user_info),
		*emails,
		*get_comment_and_log_activities(doc, user_info),
		*get_view_activities(doc, user_info),
		*get_version_activities(doc, user_info),
	]

	activities.sort(key=lambda a: (a.get("timestamp") or "", a["key"]))
	return {"activities": activities, "has_more_emails": has_more_emails}


@frappe.whitelist()
def get_more_email_activities(doctype: str, name: str | int, start: int) -> dict:
	doc = frappe.get_lazy_doc(doctype, name, check_permission=True)
	user_info: dict = {}

	emails, has_more_emails = get_email_activities(doc, user_info, start=frappe.utils.cint(start))
	emails.sort(key=lambda a: (a.get("timestamp") or "", a["key"]))
	return {"activities": emails, "has_more_emails": has_more_emails}


def get_creation_activity(doc: "Document", user_info: dict) -> list[dict]:
	frappe.utils.add_user_info({doc.owner}, user_info)
	author = author_from(doc.owner, user_info)
	return [
		{
			"type": "log",
			"key": "creation",
			"timestamp": str(doc.creation),
			"author": author,
			"data": {
				"name": "creation",
				"subtype": "created",
				"icon": "file-plus",
				"text": _("{0} created this").format(author["fullname"]),
			},
		}
	]


def get_email_activities(doc: "Document", user_info: dict, start: int = 0) -> tuple[list[dict], bool]:
	# Fetch PAGE_SIZE+1 (DESC); the extra oldest row is a sentinel for "more exist" — slice it off.
	communications = _get_communications(doc.doctype, doc.name, start=start, limit=EMAIL_PAGE_SIZE + 1)
	has_more = len(communications) > EMAIL_PAGE_SIZE
	if has_more:
		communications = communications[:EMAIL_PAGE_SIZE]
	frappe.utils.add_user_info({c.sender for c in communications if c.sender}, user_info)
	return build_email_activities(communications, user_info), has_more


def build_email_activities(communications, user_info: dict) -> list[dict]:
	out = []
	for c in communications:
		info = user_info.get(c.sender) or {}
		out.append(
			{
				"type": "email",
				"key": f"email:{c.name}",
				"timestamp": str(c.communication_date or c.creation),
				"author": {
					"email": c.sender,
					"fullname": c.sender_full_name or info.get("fullname") or c.sender,
					"image": info.get("image"),
				},
				"data": {
					"name": c.name,
					"subject": c.subject,
					"sender": c.sender,
					"to": c.recipients,
					"cc": c.cc,
					"bcc": c.bcc,
					"content": c.content,
					"deliveryStatus": c.delivery_status,
					"attachments": parse_email_attachments(c.attachments),
				},
			}
		)
	return out


def parse_email_attachments(attachments) -> list[dict]:
	if not attachments:
		return []
	parsed = json.loads(attachments) if isinstance(attachments, str) else attachments
	out = []
	for a in parsed or []:
		file_url = a.get("file_url")
		out.append(
			{
				"file_url": file_url,
				"file_name": a.get("file_name") or (file_url.split("/")[-1] if file_url else None),
				"is_private": a.get("is_private"),
			}
		)
	return out


def get_comment_and_log_activities(doc: "Document", user_info: dict) -> list[dict]:
	comment_log_data = frappe._dict()
	add_comments(doc, comment_log_data)

	all_rows = (
		comment_log_data.comments
		+ comment_log_data.assignment_logs
		+ comment_log_data.attachment_logs
		+ comment_log_data.info_logs
		+ comment_log_data.like_logs
		+ comment_log_data.workflow_logs
	)
	frappe.utils.add_user_info({c.owner for c in all_rows if c.owner}, user_info)

	out = []

	for c in comment_log_data.comments:
		author = author_from(c.owner, user_info)
		out.append(
			{
				"type": "comment",
				"key": f"comment:{c.name}",
				"timestamp": str(c.creation),
				"author": author,
				"data": {"name": c.name, "content": c.content},  # already markdown'd by add_comments
			}
		)

	for c in comment_log_data.attachment_logs:
		out.append(attachment_log_activity(c, author_from(c.owner, user_info)))

	for c in comment_log_data.like_logs:
		author = author_from(c.owner, user_info)
		out.append(log_activity(c, author, "like", "heart", _("{0} liked").format(author["fullname"])))

	for c in comment_log_data.assignment_logs:
		author = author_from(c.owner, user_info)
		if c.comment_type == "Assigned":
			out.append(log_activity(c, author, "assigned", "user-plus", activity_text(c.content)))
		else:
			out.append(
				log_activity(c, author, "assignment_completed", "circle-check", activity_text(c.content))
			)

	for c in comment_log_data.workflow_logs:
		author = author_from(c.owner, user_info)
		out.append(
			log_activity(
				c,
				author,
				"workflow",
				"git-branch",
				f"{author['fullname']} {activity_text(c.content)}",
			)
		)

	for c in comment_log_data.info_logs:
		author = author_from(c.owner, user_info)
		out.append(
			log_activity(c, author, "info", "info", f"{author['fullname']} {activity_text(c.content)}")
		)

	return out


def author_from(owner: str, user_info: dict) -> dict:
	info = user_info.get(owner) or {}
	return {
		"email": info.get("email") or owner,
		"fullname": info.get("fullname") or owner,
		"image": info.get("image"),
	}


def activity_text(html: str | None) -> str:
	return frappe.utils.strip_html(html or "").strip()


def attachment_log_activity(c, author: dict) -> dict:
	action = "removed" if c.comment_type == "Attachment Removed" else "added"
	content = c.content or ""
	href = re.search(r"""href=['"]([^'"]+)['"]""", content)
	file_url = href.group(1) if (href and action == "added") else None
	return {
		"type": "attachment_log",
		"key": f"attachment:{c.name}",
		"timestamp": str(c.creation),
		"author": author,
		"data": {
			"name": c.name,
			"action": action,
			"fileName": activity_text(content),
			"fileUrl": file_url,
			# private files live under /private/… — a stabler signal than the `fa-lock` icon
			"isPrivate": bool(file_url and file_url.startswith("/private/")),
		},
	}


def log_activity(c, author: dict, subtype: str, icon: str, text: str) -> dict:
	return {
		"type": "log",
		"key": f"log:{c.name}",
		"timestamp": str(c.creation),
		"author": author,
		"data": {"name": c.name, "subtype": subtype, "icon": icon, "text": text},
	}


def get_view_activities(doc: "Document", user_info: dict) -> list[dict]:
	views = get_view_logs(doc)
	frappe.utils.add_user_info({v.owner for v in views if v.owner}, user_info)

	out = []
	for v in views:
		author = author_from(v.owner, user_info)
		out.append(
			{
				"type": "log",
				"key": f"view:{v.name}",
				"timestamp": str(v.creation),
				"author": author,
				"data": {
					"name": v.name,
					"subtype": "view",
					"icon": "eye",
					"text": _("{0} viewed this").format(author["fullname"]),
				},
			}
		)
	return out


# Fieldtypes shown as "updated {field}" instead of a from → to diff.
LONG_TEXT_FIELDTYPES = {
	"Text",
	"Small Text",
	"Long Text",
	"Text Editor",
	"Code",
	"HTML Editor",
	"Markdown Editor",
	"JSON",
}


def get_version_activities(doc: "Document", user_info: dict) -> list[dict]:
	versions = get_versions(doc)
	if not versions:
		return []

	doctype = doc.doctype
	meta = doc.meta
	permitted = set(
		frappe.model.get_permitted_fields(doctype, user=frappe.session.user, permission_type="read")
	)  # handles field level perms aswell

	frappe.utils.add_user_info({v.owner for v in versions if v.owner}, user_info)

	child_cache: dict[str, tuple[set, "frappe.Meta"]] = {}

	result = []
	for v in versions:
		data = json.loads(v.data or "{}")
		changes: list[dict] = []

		for fieldname, old, new in data.get("changed", []):
			if fieldname == "docstatus":
				if new == 1:
					changes.append(format_docstatus_change(_("submitted this document")))
				elif new == 2:
					changes.append(format_docstatus_change(_("cancelled this document")))
				continue

			df = is_field_visible(meta, permitted, fieldname)
			if not df:
				continue

			changes.append(format_version_change(df, fieldname, old, new))

		for key, value in (
			("added", _("added {0} row(s) to {1}")),
			("removed", _("removed {0} row(s) from {1}")),
		):
			counts: dict[str, int] = {}
			for table_fieldname, _row in data.get(key, []):
				counts[table_fieldname] = counts.get(table_fieldname, 0) + 1
			for table_fieldname, count in counts.items():
				df = is_field_visible(meta, permitted, table_fieldname)
				if not df:
					continue
				changes.append(format_docstatus_change(value.format(count, _(df.label or table_fieldname))))

		for entry in data.get("row_changed", []):
			# get_diff order is (table_fieldname, row_index, row_name, changes); version.py docstring is wrong
			table_fieldname, row_index, _row_name, child_changes = entry
			df = is_field_visible(meta, permitted, table_fieldname)
			if not df:
				continue

			child_dt = df.options
			if child_dt not in child_cache:
				child_cache[child_dt] = (
					set(
						frappe.model.get_permitted_fields(
							child_dt,
							parenttype=doctype,
							user=frappe.session.user,
							permission_type="read",
						)
					),
					frappe.get_meta(child_dt),
				)
			child_permitted, child_meta = child_cache[child_dt]

			for cfield, _cold, cnew in child_changes:
				cdf = is_field_visible(child_meta, child_permitted, cfield)
				if not cdf:
					continue
				changes.append(
					format_docstatus_change(
						_("set {0} to {1} in row #{2}").format(
							_(cdf.label or cfield),
							truncate_value(cnew),
							row_index + 1,
						)
					)
				)

		author = author_from(v.owner, user_info)
		for idx, change in enumerate(changes):
			change["name"] = f"{v.name}-{idx}"
			result.append(
				{
					"type": "version",
					"key": f"version:{v.name}-{idx}",
					"timestamp": str(v.creation),
					"author": author,
					"data": change,
				}
			)

	return result


def format_version_change(df, fieldname: str, old, new) -> dict:
	label = _(df.label or fieldname)
	# send the full stripped value; the frontend clips it for display
	old_s = display_value(old)
	new_s = display_value(new)

	# long-text/HTML edits and clears can't show values — ship a finished phrase
	if df.fieldtype in LONG_TEXT_FIELDTYPES:
		return {"fieldname": fieldname, "type": "phrase", "text": _("updated {0}").format(label)}
	if old_s and not new_s:
		return {"fieldname": fieldname, "type": "phrase", "text": _("cleared {0}").format(label)}

	# diff: the frontend lays out the value(s). `from` omitted ⇒ set-from-blank (no arrow)
	if old_s:
		return {
			"fieldname": fieldname,
			"type": "diff",
			"prefix": _("changed {0}").format(label),
			"from": old_s,
			"to": new_s,
		}
	return {
		"fieldname": fieldname,
		"type": "diff",
		"prefix": _("set {0} to").format(label),
		"to": new_s,
	}


def format_docstatus_change(text: str) -> dict:
	"""A doc-level change (submit/cancel/table rows) — a phrase that never folds."""
	return {"fieldname": None, "type": "phrase", "text": text}


def is_field_visible(meta, permitted: set, fieldname: str):
	"""The docfield, or None if it's not readable or is hidden from the timeline."""
	if fieldname not in permitted:
		return None
	df = meta.get_field(fieldname)
	if not df or (df.hidden and not df.show_on_timeline):
		return None
	return df


def display_value(value) -> str:
	"""Full HTML-stripped value; the frontend handles clipping."""
	if value is None or value == "":
		return ""
	return frappe.utils.strip_html(str(value)).strip()


def truncate_value(value) -> str:
	if value is None or value == "":
		return ""
	s = frappe.utils.strip_html(str(value))
	return s[:40] + "…" if len(s) > 40 else s
