# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE
"""Normalized activity feed for a document — the data source behind the Vue
ActivityTimeline. Folds what the desk spreads across get_docinfo and the Version
doctype (emails, comments, attachment logs, audit lines, field-change history)
into one flat, permission-safe list already shaped for the renderer."""

import json
import re

import frappe
import frappe.utils
from frappe import _
from frappe.desk.form.load import _get_communications
from frappe.model.document import Document


def format_version_value(value, df) -> str:
	"""Readable, length-capped, html-stripped string for a single diff value."""
	if value is None or value == "":
		return ""
	s = frappe.utils.strip_html(str(value))
	if len(s) > 40:
		s = s[:40] + "…"
	return s


def get_version_activities(doc: "Document", user_info: dict) -> list[dict]:
	"""Permission-safe, label-resolved field-change history from the Version doctype,
	normalized to the timeline's `version` activity shape.

	Mirrors desk's version_timeline_content_builder.js but applies a server-side
	field-level permission filter (the Python equivalent of get_field_display_status):
	only fields the user may read (per get_permitted_fields, which encodes permlevel +
	role perms) are surfaced.
	"""
	doctype, name = doc.doctype, doc.name
	meta = doc.meta
	if not meta.track_changes:
		return []

	# the permission filter — computed once for the parent doctype
	permitted = set(
		frappe.model.get_permitted_fields(doctype, user=frappe.session.user, permission_type="read")
	)

	versions = frappe.get_all(
		"Version",
		filters={"ref_doctype": doctype, "docname": str(name)},
		fields=["name", "owner", "creation", "data"],
		order_by="creation desc",
		limit=10,
	)

	frappe.utils.add_user_info({v.owner for v in versions if v.owner}, user_info)

	# child doctype permitted-field sets, cached across versions
	child_permitted_cache: dict[str, set] = {}
	child_meta_cache: dict[str, "frappe.Meta"] = {}

	# one row PER individual change (author-less phrase), so the frontend can show
	# each as its own line ("{user} set Status to Resolved") with its own timestamp
	# and group consecutive same-author changes into a "+N changes" collapsible.
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

			# permission filter: drop fields the user may not read
			if fieldname not in permitted:
				continue

			df = meta.get_field(fieldname)
			if not df:
				continue
			if df.hidden and not df.show_on_timeline:
				continue

			texts.append(_("set {0} to {1}").format(_(df.label or fieldname), format_version_value(new, df)))

		# added / removed rows: group by child table, count rows
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
			# get_diff appends (table_fieldname, row_index, row_name, changes); the
			# version.py docstring lists row_name/row_index swapped — the code (and
			# desk's version_timeline_content_builder.js, which uses row[1] + 1 as the
			# displayed row number) is authoritative.
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

		info = user_info.get(v.owner) or {}
		author = {
			"email": v.owner,
			"fullname": info.get("fullname") or frappe.utils.get_fullname(v.owner),
			"image": info.get("image"),
		}
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


def activity_text(html: str | None) -> str:
	"""Readable plaintext for an audit/attachment comment (desk content is HTML)."""
	return frappe.utils.strip_html(html or "").strip()


def author_from(owner: str, user_info: dict) -> dict:
	"""UserInfo envelope for a comment/audit owner, falling back to the id itself."""
	info = user_info.get(owner) or {}
	return {
		"email": info.get("email") or owner,
		"fullname": info.get("fullname") or owner,
		"image": info.get("image"),
	}


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


def get_email_activities(doc: "Document", user_info: dict) -> list[dict]:
	"""Communications + automated messages → `email` activities."""
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


def attachment_log_activity(c, author: dict) -> dict:
	"""Comment-based attachment log → structured `attachment_log` activity. Desk
	content is `<a href='{url}'>{name}</a>` (+ optional fa-lock <i>) for adds, and
	a bare filename for removals."""
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


def audit_activity(c, author: dict, subtype: str, icon: str, text: str) -> dict:
	return {
		"type": "audit",
		"key": f"audit:{c.name}",
		"timestamp": str(c.creation),
		"author": author,
		"data": {"name": c.name, "subtype": subtype, "icon": icon, "text": text},
	}


def get_comment_and_audit_activities(doc: "Document", user_info: dict) -> list[dict]:
	"""All Comment rows for the doc, bucketed by comment_type into `comment`,
	`attachment_log` and `audit` activities (likes / assignments / workflow / info).
	The desk previously did this bucketing in add_comments + the client; centralizing
	it here keeps the composable a thin sorter."""
	comments = frappe.get_all(
		"Comment",
		fields=["name", "creation", "content", "owner", "comment_type"],
		filters={"reference_doctype": doc.doctype, "reference_name": doc.name},
	)
	frappe.utils.add_user_info({c.owner for c in comments if c.owner}, user_info)

	out = []
	for c in comments:
		author = author_from(c.owner, user_info)
		match c.comment_type:
			case "Comment":
				out.append(
					{
						"type": "comment",
						"key": f"comment:{c.name}",
						"timestamp": str(c.creation),
						"author": author,
						"data": {"name": c.name, "content": frappe.utils.markdown(c.content)},
					}
				)
			case "Attachment" | "Attachment Removed":
				out.append(attachment_log_activity(c, author))
			case "Like":
				out.append(
					audit_activity(c, author, "like", "heart", _("{0} liked").format(author["fullname"]))
				)
			case "Assigned":
				out.append(audit_activity(c, author, "assigned", "user-plus", activity_text(c.content)))
			case "Assignment Completed":
				out.append(
					audit_activity(
						c, author, "assignment_completed", "circle-check", activity_text(c.content)
					)
				)
			case "Workflow":
				out.append(
					audit_activity(
						c,
						author,
						"workflow",
						"git-branch",
						f"{author['fullname']} {activity_text(c.content)}",
					)
				)
			case "Info" | "Edit" | "Label":
				out.append(
					audit_activity(
						c, author, "info", "info", f"{author['fullname']} {activity_text(c.content)}"
					)
				)
	return out


def get_view_activities(doc: "Document", user_info: dict) -> list[dict]:
	"""View Log entries → `audit` activities (subtype 'view', "{user} viewed this").
	Gated by the doctype's track_views; this is the timestamped source for "seen",
	since the doc's _seen list carries no per-user timestamp. Capped to the most
	recent rows so a heavily-viewed doc doesn't flood the feed."""
	if not doc.meta.track_views:
		return []

	views = frappe.get_all(
		"View Log",
		filters={"reference_doctype": doc.doctype, "reference_name": str(doc.name)},
		fields=["name", "creation", "owner"],
		order_by="creation desc",
		limit=50,
	)
	frappe.utils.add_user_info({v.owner for v in views if v.owner}, user_info)

	out = []
	for v in views:
		author = author_from(v.owner, user_info)
		out.append(
			{
				"type": "audit",
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


@frappe.whitelist()
def get_activity_timeline(doctype: str, name: str | int) -> list[dict]:
	"""Normalized, permission-safe activity feed for a document — the single data
	source behind the Vue ActivityTimeline.

	Returns a flat, chronologically-ascending list of activities already in the
	shape the renderer expects (type / key / timestamp / author / data), folding in
	what the desk previously spread across get_docinfo and the Version doctype:
	emails, comments, attachment add/remove logs, audit lines (likes, assignments,
	workflow, info) and field-change history. All HTML stripping, comment_type
	bucketing and label/permission resolution happens here so the client composable
	stays a thin sorter (it only groups consecutive versions and applies asc/desc)."""
	doc = frappe.get_lazy_doc(doctype, name, check_permission=True)

	# one user_info map shared by every author lookup below
	user_info: dict = {}

	activities = [
		*get_email_activities(doc, user_info),
		*get_comment_and_audit_activities(doc, user_info),
		*get_view_activities(doc, user_info),
		*get_version_activities(doc, user_info),
	]

	# ascending by frappe-format timestamp (lexicographic is correct for that
	# format), stable `key` tiebreak. The client groups consecutive versions on this
	# ascending order before reversing for desc, so ascending is the contract.
	activities.sort(key=lambda a: (a.get("timestamp") or "", a["key"]))
	return activities
