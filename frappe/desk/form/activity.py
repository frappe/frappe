# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

import json
import re

import frappe
import frappe.utils
from frappe import _
from frappe.desk.form.load import (
	_get_communications,
	add_comments,
	get_milestones,
	get_versions,
	get_view_logs,
)
from frappe.model.document import Document

# Emails and milestones are paged newest-first; the remaining sources load in full.
EMAIL_PAGE_SIZE = 20
MILESTONE_PAGE_SIZE = 20


@frappe.whitelist()
def get_activity_timeline(
	doctype: str,
	name: str | int,
	visible_types: list[str | dict[str, list[str]]] | str | None = None,
) -> dict:
	"""`visible_types` limits sources server-side so pagination math stays correct."""
	doc = frappe.get_lazy_doc(doctype, name, check_permission=True)
	user_info: dict = {}  # cache user lookups

	if isinstance(visible_types, str):
		visible_types = frappe.parse_json(visible_types)
	visible, version_fields = parse_visible_types(visible_types)

	def show(*types: str) -> bool:
		return visible is None or not visible.isdisjoint(types)

	emails, has_more_emails = get_email_activities(doc, user_info) if show("email") else ([], False)
	milestones, has_more_milestones, next_milestone_start = (
		get_milestone_activities(doc, user_info) if show("log") else ([], False, 0)
	)
	activities = [
		*(get_creation_activity(doc, user_info) if show("log") else []),
		*(get_edit_activity(doc, user_info) if show("log") else []),
		*emails,
		*(get_comment_and_log_activities(doc, user_info) if show("comment", "log", "attachment_log") else []),
		*(get_view_activities(doc, user_info) if show("log") else []),
		*milestones,
		*(get_version_activities(doc, user_info, version_fields) if show("version") else []),
	]
	if visible is not None:
		# comment/log/attachment_log share one fetcher; drop the leftover types here
		activities = [a for a in activities if a["type"] in visible]

	activities.sort(key=lambda a: (a.get("timestamp") or "", a["key"]))
	return {
		"activities": activities,
		"has_more_emails": has_more_emails,
		"has_more_milestones": has_more_milestones,
		"next_milestone_start": next_milestone_start,
	}


def parse_visible_types(visible_types) -> tuple[set[str] | None, list[str] | None]:
	"""["email", {"version": ["status"]}] → (type set, version-field allowlist)."""
	if not visible_types:
		return None, None
	types: set[str] = set()
	version_fields = None
	for entry in visible_types:
		if isinstance(entry, dict):
			for activity_type, fields in entry.items():
				types.add(activity_type)
				if activity_type == "version":
					version_fields = fields
		else:
			types.add(entry)
	return types, version_fields


@frappe.whitelist()
def get_more_email_activities(doctype: str, name: str | int, start: int) -> dict:
	doc = frappe.get_lazy_doc(doctype, name, check_permission=True)
	user_info: dict = {}

	emails, has_more_emails = get_email_activities(doc, user_info, start=frappe.utils.cint(start))
	emails.sort(key=lambda a: (a.get("timestamp") or "", a["key"]))
	return {"activities": emails, "has_more_emails": has_more_emails}


@frappe.whitelist()
def get_more_milestone_activities(doctype: str, name: str | int, start: int) -> dict:
	doc = frappe.get_lazy_doc(doctype, name, check_permission=True)
	user_info: dict = {}

	milestones, has_more, next_start = get_milestone_activities(
		doc, user_info, start=frappe.utils.cint(start)
	)
	milestones.sort(key=lambda a: (a.get("timestamp") or "", a["key"]))
	return {
		"activities": milestones,
		"has_more_milestones": has_more,
		"next_milestone_start": next_start,
	}


def get_creation_activity(doc: "Document", user_info: dict) -> list[dict]:
	frappe.utils.add_user_info({doc.owner}, user_info)
	author = get_author_info(doc.owner, user_info)
	msg = get_creation_msg(doc.owner, author["fullname"])
	return [
		{
			"type": "log",
			"key": "creation",
			"timestamp": str(doc.creation),
			"author": author,
			"data": {
				"name": "creation",
				"subtype": "created",
				"text": msg,
			},
		}
	]


def get_creation_msg(owner: str, fullname: str):
	# "You" keys off the session user; everyone else shows the resolved fullname (not the raw user id)
	if frappe.session.user == owner:
		return _("You created this document")
	return _("{0} created this document").format(fullname)


def get_edit_activity(doc: "Document", user_info: dict) -> list[dict]:
	"""The last edit, which is the only sign of one on a doctype that tracks no changes."""
	if not doc.modified or str(doc.modified) == str(doc.creation):
		return []

	frappe.utils.add_user_info({doc.modified_by}, user_info)
	author = get_author_info(doc.modified_by, user_info)
	return [
		{
			"type": "log",
			"key": "edited",
			"timestamp": str(doc.modified),
			"author": author,
			"data": {
				"name": "edited",
				"subtype": "edited",
				"text": get_edit_msg(doc.modified_by, author["fullname"]),
			},
		}
	]


def get_edit_msg(modified_by: str, fullname: str):
	if frappe.session.user == modified_by:
		return _("You last edited this document")
	return _("{0} last edited this document").format(fullname)


def get_email_activities(doc: "Document", user_info: dict, start: int = 0) -> tuple[list[dict], bool]:
	# Fetch PAGE_SIZE+1 (DESC); the extra oldest row signals "more exist".
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
	try:
		parsed = json.loads(attachments) if isinstance(attachments, str) else attachments
	except (json.JSONDecodeError, TypeError):
		return []
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
		+ comment_log_data.shared
	)
	frappe.utils.add_user_info({c.owner for c in all_rows if c.owner}, user_info)

	out = []

	attachments = get_comment_attachments([c.name for c in comment_log_data.comments])
	for c in comment_log_data.comments:
		author = get_author_info(c.owner, user_info)
		out.append(
			{
				"type": "comment",
				"key": f"comment:{c.name}",
				"timestamp": str(c.creation),
				"author": author,
				"data": {
					"name": c.name,
					"content": c.content,
					"attachments": attachments.get(c.name, []),
				},
			}
		)

	for c in comment_log_data.attachment_logs:
		out.append(attachment_log_activity(c, get_author_info(c.owner, user_info)))

	for c in comment_log_data.like_logs:
		author = get_author_info(c.owner, user_info)
		out.append(add_activity_record(c, author, "like", _("{0} liked").format(author["fullname"])))

	for c in comment_log_data.assignment_logs:
		author = get_author_info(c.owner, user_info)
		text = activity_text(c.content)
		assignee = assignee_from_assignment(text, c.comment_type)
		if c.comment_type == "Assigned":
			out.append(add_activity_record(c, author, "assigned", text, assignee=assignee))
		else:
			out.append(add_activity_record(c, author, "assignment_completed", text, assignee=assignee))

	for c in comment_log_data.workflow_logs:
		author = get_author_info(c.owner, user_info)
		out.append(
			add_activity_record(
				c,
				author,
				"workflow",
				f"{author['fullname']} {activity_text(c.content)}",
			)
		)

	for c in comment_log_data.info_logs:
		author = get_author_info(c.owner, user_info)
		out.append(add_activity_record(c, author, "info", f"{author['fullname']} {activity_text(c.content)}"))

	# docshare.py writes these already naming both the actor and who was shared with.
	for c in comment_log_data.shared:
		author = get_author_info(c.owner, user_info)
		out.append(add_activity_record(c, author, "shared", activity_text(c.content)))

	return out


def get_comment_attachments(comment_names: list[str]) -> dict[str, list[dict]]:
	"""Files attached to the given comments, batched, shaped like email attachments."""
	if not comment_names:
		return {}
	out: dict[str, list[dict]] = {}
	for f in frappe.get_all(
		"File",
		filters={"attached_to_doctype": "Comment", "attached_to_name": ("in", comment_names)},
		fields=["file_url", "file_name", "is_private", "attached_to_name"],
		order_by="creation",
	):
		out.setdefault(f.attached_to_name, []).append(
			{"file_url": f.file_url, "file_name": f.file_name, "is_private": f.is_private}
		)
	return out


def get_author_info(owner: str, user_info: dict) -> dict:
	info = user_info.get(owner) or {}
	return {
		"email": info.get("email") or owner,
		"fullname": info.get("fullname") or owner,
		"image": info.get("image"),
	}


def activity_text(html: str | None) -> str:
	return frappe.utils.strip_html(html or "").strip()


def assignee_from_assignment(text: str, comment_type: str) -> str | None:
	"""The assignee named in an assignment-log comment, or None.

	Extracted locale-safely from todo.py's own `_()` templates (copied verbatim),
	not by parsing English; None when the assignee is the actor or nothing matches.
	"""
	if comment_type == "Assigned":
		# (template, assignee placeholder index, or None when it's the actor).
		# Self-assign tried first so "{0} assigned {1}: {2}" can't misread it.
		templates = (
			(_("{0} self assigned this task: {1}"), None),
			(_("{0} assigned {1}: {2}"), 1),
		)
	else:
		templates = (
			(_("{0} removed their assignment."), None),
			(_("Assignment of {0} removed by {1}"), 0),
		)

	for template, assignee_idx in templates:
		groups = match_format_template(template, text)
		if groups is None:
			continue
		return None if assignee_idx is None else groups.get(assignee_idx)
	return None


def match_format_template(template: str, text: str) -> dict[int, str] | None:
	"""Match `text` against a translated `str.format` template.

	Each `{n}` becomes a non-greedy capture; returns {placeholder_index: value}
	(keyed by original index so reordered locales still resolve), or None.
	"""
	pattern = ["^"]
	order: list[int] = []
	for part in re.split(r"(\{\d+\})", template):
		m = re.fullmatch(r"\{(\d+)\}", part)
		if m:
			order.append(int(m.group(1)))
			pattern.append("(.+?)")
		else:
			pattern.append(re.escape(part))
	pattern.append(r"\Z")

	match = re.match("".join(pattern), text, re.DOTALL)
	if not match:
		return None
	return {placeholder: match.group(i + 1) for i, placeholder in enumerate(order)}


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


def add_activity_record(c, author: dict, subtype: str, text: str, assignee: str | None = None) -> dict:
	data = {"name": c.name, "subtype": subtype, "text": text}
	# Purely additive: only assignment logs pass an assignee; others leave it absent.
	if assignee is not None:
		data["assignee"] = assignee
	return {
		"type": "log",
		"key": f"log:{c.name}",
		"timestamp": str(c.creation),
		"author": author,
		"data": data,
	}


def get_view_activities(doc: "Document", user_info: dict) -> list[dict]:
	views = get_view_logs(doc)
	frappe.utils.add_user_info({v.owner for v in views if v.owner}, user_info)

	out = []
	for v in views:
		author = get_author_info(v.owner, user_info)
		out.append(
			{
				"type": "log",
				"key": f"view:{v.name}",
				"timestamp": str(v.creation),
				"author": author,
				"data": {
					"name": v.name,
					"subtype": "view",
					"text": _("{0} viewed this").format(author["fullname"]),
				},
			}
		)
	return out


def get_milestone_activities(
	doc: "Document", user_info: dict, start: int = 0
) -> tuple[list[dict], bool, int]:
	# Fetch PAGE_SIZE+1 (DESC); the extra oldest row signals "more exist".
	milestones = get_milestones(doc.doctype, doc.name, start=start, limit=MILESTONE_PAGE_SIZE + 1)
	has_more = len(milestones) > MILESTONE_PAGE_SIZE
	if has_more:
		milestones = milestones[:MILESTONE_PAGE_SIZE]
	next_start = start + len(milestones)
	if not milestones:
		return [], False, next_start

	# A milestone names a field and its value, so it needs the same read check as a version.
	permitted = readable_permlevels(doc.meta)
	frappe.utils.add_user_info({m.owner for m in milestones if m.owner}, user_info)

	out = []
	for m in milestones:
		df = is_field_visible(doc.meta, permitted, m.track_field)
		if not df:
			continue

		author = get_author_info(m.owner, user_info)
		out.append(
			{
				"type": "log",
				"key": f"milestone:{m.name}",
				"timestamp": str(m.creation),
				"author": author,
				"data": {
					"name": m.name,
					"subtype": "milestone",
					"text": _("{0} changed {1} to {2}").format(
						author["fullname"], _(df.label or m.track_field), m.value
					),
				},
			}
		)
	# next_start counts rows read, not rows returned: a field the user cannot read drops a row here,
	# so an offset the client derived from what it rendered would skip the rows behind it.
	return out, has_more, next_start


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


def get_version_activities(
	doc: "Document", user_info: dict, allowed_fields: list[str] | None = None
) -> list[dict]:
	versions = get_versions(doc)
	if not versions:
		return []

	doctype = doc.doctype
	meta = doc.meta
	permitted = readable_permlevels(meta)

	frappe.utils.add_user_info({v.owner for v in versions if v.owner}, user_info)

<<<<<<< HEAD
	child_cache: dict[str, tuple[set, frappe.Meta]] = {}
=======
	child_cache: dict[str, tuple[set | None, "frappe.Meta"]] = {}
>>>>>>> 2b620e0 (fix: improve timeline component)

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

		changes.extend(get_child_table_changes(data, doctype, meta, permitted, child_cache))

		# allowlist means "only these fields": doc-level rows (fieldname None) drop too
		if allowed_fields is not None:
			changes = [c for c in changes if c.get("fieldname") in allowed_fields]

		author = get_author_info(v.owner, user_info)
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


def format_docstatus_change(text: str, fieldname: str | None = None) -> dict:
	"""A finished phrase; child-table rows carry the table's fieldname, submit/cancel carry none."""
	return {"fieldname": fieldname, "type": "phrase", "text": text}


def get_child_table_changes(
	data: dict,
	doctype: str,
	meta,
	permitted: set | None,
	child_cache: dict,
) -> list[dict]:
	"""Child-table entries of a version — row adds/removes as per-table counts, plus
	field edits inside rows. All carry the parent table's fieldname."""
	changes: list[dict] = []

	for key, template in (
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
			changes.append(
				format_docstatus_change(
					template.format(count, _(df.label or table_fieldname)), fieldname=table_fieldname
				)
			)

	for entry in data.get("row_changed", []):
		# get_diff order is (table_fieldname, row_index, row_name, changes); version.py docstring is wrong
		table_fieldname, row_index, _row_name, child_changes = entry
		df = is_field_visible(meta, permitted, table_fieldname)
		if not df:
			continue

		child_dt = df.options
		if child_dt not in child_cache:
			child_meta = frappe.get_meta(child_dt)
			child_cache[child_dt] = (readable_permlevels(child_meta, parenttype=doctype), child_meta)
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
					),
					fieldname=table_fieldname,
				)
			)

	return changes


def readable_permlevels(meta, parenttype: str | None = None) -> set[int] | None:
	"""Permlevels the session user can read (desk's field_display_status model);
	None ⇒ no permission rows defined, everything readable."""
	if not meta.get_permissions(parenttype):
		return None
	levels = set(meta.get_permlevel_access("read", parenttype, user=frappe.session.user))
	# reads granted via a share carry no role row; they see permlevel-0 fields
	if 0 not in levels and frappe.share.get_shared(
		parenttype or meta.name, frappe.session.user, rights=["read"], limit=1
	):
		levels.add(0)
	return levels


def is_field_visible(meta, permlevels: set | None, fieldname: str):
	"""The docfield, or None if it's not readable or is hidden from the timeline."""
	df = meta.get_field(fieldname)
	if not df or (df.hidden and not df.show_on_timeline):
		return None
	if permlevels is not None and df.permlevel not in permlevels:
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
