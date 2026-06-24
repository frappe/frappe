# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

import json
import re

import frappe
import frappe.utils
from frappe import _
from frappe.desk.form.load import _get_communications, add_comments, get_versions, get_view_logs
from frappe.model.document import Document


@frappe.whitelist()
def get_activity_timeline(doctype: str, name: str | int) -> list[dict]:
	doc = frappe.get_lazy_doc(doctype, name, check_permission=True)
	user_info: dict = {}

	activities = [
		*get_creation_activity(doc, user_info),
		*get_email_activities(doc, user_info),
		*get_comment_and_log_activities(doc, user_info),
		*get_view_activities(doc, user_info),
		*get_version_activities(doc, user_info),
	]

	activities.sort(key=lambda a: (a.get("timestamp") or "", a["key"]))
	return activities


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


def get_email_activities(doc: "Document", user_info: dict) -> list[dict]:
	communications = _get_communications(doc.doctype, doc.name, limit=21)
	frappe.utils.add_user_info({c.sender for c in communications if c.sender}, user_info)

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
	return {
		"type": "attachment_log",
		"key": f"attachment:{c.name}",
		"timestamp": str(c.creation),
		"author": author,
		"data": {
			"name": c.name,
			"action": action,
			"fileName": activity_text(content),
			"fileUrl": href.group(1) if (href and action == "added") else None,
			"isPrivate": "fa-lock" in content,
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


def get_version_activities(doc: "Document", user_info: dict) -> list[dict]:
	versions = get_versions(doc)
	if not versions:
		return []

	doctype = doc.doctype
	meta = doc.meta
	permitted = set(
		frappe.model.get_permitted_fields(doctype, user=frappe.session.user, permission_type="read")
	)

	frappe.utils.add_user_info({v.owner for v in versions if v.owner}, user_info)

	child_permitted_cache: dict[str, set] = {}
	child_meta_cache: dict[str, "frappe.Meta"] = {}

	result = []
	for v in versions:
		data = json.loads(v.data or "{}")
		texts: list[str] = []

		for fieldname, _old, new in data.get("changed", []):
			if fieldname == "docstatus":
				if new == 1:
					texts.append(_("submitted this document"))
				elif new == 2:
					texts.append(_("cancelled this document"))
				continue

			if fieldname not in permitted:
				continue

			df = meta.get_field(fieldname)
			if not df:
				continue
			if df.hidden and not df.show_on_timeline:
				continue

			texts.append(_("set {0} to {1}").format(_(df.label or fieldname), format_version_value(new, df)))

		for key, label_fmt in (
			("added", _("added {0} row(s) to {1}")),
			("removed", _("removed {0} row(s) from {1}")),
		):
			counts: dict[str, int] = {}
			for table_fieldname, _row in data.get(key, []):
				counts[table_fieldname] = counts.get(table_fieldname, 0) + 1
			for table_fieldname, count in counts.items():
				if table_fieldname not in permitted:
					continue
				df = meta.get_field(table_fieldname)
				if not df:
					continue
				if df.hidden and not df.show_on_timeline:
					continue
				texts.append(label_fmt.format(count, _(df.label or table_fieldname)))

		for entry in data.get("row_changed", []):
			# get_diff order is (table_fieldname, row_index, row_name, changes) —
			# version.py docstring has row_name/row_index swapped; the code is authoritative
			table_fieldname, row_index, _row_name, child_changes = entry
			if table_fieldname not in permitted:
				continue
			df = meta.get_field(table_fieldname)
			if not df:
				continue
			if df.hidden and not df.show_on_timeline:
				continue

			child_dt = df.options
			if child_dt not in child_permitted_cache:
				child_permitted_cache[child_dt] = set(
					frappe.model.get_permitted_fields(
						child_dt,
						parenttype=doctype,
						user=frappe.session.user,
						permission_type="read",
					)
				)
				child_meta_cache[child_dt] = frappe.get_meta(child_dt)
			child_permitted = child_permitted_cache[child_dt]
			child_meta = child_meta_cache[child_dt]

			for cfield, _cold, cnew in child_changes:
				if cfield not in child_permitted:
					continue
				cdf = child_meta.get_field(cfield)
				if not cdf:
					continue
				if cdf.hidden and not cdf.show_on_timeline:
					continue
				texts.append(
					_("set {0} to {1} in row #{2}").format(
						_(cdf.label or cfield),
						format_version_value(cnew, cdf),
						row_index + 1,
					)
				)

		author = author_from(v.owner, user_info)
		for idx, text in enumerate(texts):
			result.append(
				{
					"type": "version",
					"key": f"version:{v.name}-{idx}",
					"timestamp": str(v.creation),
					"author": author,
					"data": {"name": f"{v.name}-{idx}", "text": text},
				}
			)

	return result


def format_version_value(value, df) -> str:
	if value is None or value == "":
		return ""
	s = frappe.utils.strip_html(str(value))
	if len(s) > 40:
		s = s[:40] + "…"
	return s
