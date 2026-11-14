import json

import frappe


def execute():
	"""Backfill legacy `Studio AI Session.messages_json` blobs into `Studio AI Message`
	rows. The messages_json field has since been dropped, so a site created after that
	removal has nothing to backfill — bail before touching the missing column."""
	if not frappe.db.has_column("Studio AI Session", "messages_json"):
		return

	# Read the column raw — it's no longer in the doctype JSON, so query the table directly
	# instead of through get_all, which resolves fields against the doctype meta.
	sessions = frappe.db.sql(
		"SELECT name, messages_json FROM `tabStudio AI Session` "
		"WHERE messages_json IS NOT NULL AND messages_json != '' AND messages_json != '[]'",
		as_dict=True,
	)
	for session in sessions:
		if frappe.db.exists("Studio AI Message", {"session": session.name}):
			continue
		for message in parse_messages(session.messages_json):
			create_message_row(session.name, message)


def parse_messages(messages_json: str | None) -> list[dict]:
	try:
		messages = json.loads(messages_json or "[]")
	except (json.JSONDecodeError, TypeError):
		return []
	return [m for m in messages if isinstance(m, dict)] if isinstance(messages, list) else []


def create_message_row(session: str, message: dict):
	metadata = message.get("metadata")
	metadata = metadata if isinstance(metadata, dict) else {}
	# `status` gets its own column for cheap filtered queries; the rest stays in metadata.
	status = (metadata.get("status") or "").strip()
	meta_clean = {key: value for key, value in metadata.items() if key != "status"}

	doc = frappe.get_doc(
		{
			"doctype": "Studio AI Message",
			"session": session,
			"role": message.get("role") or "user",
			"content": message.get("content") or "",
			"message_type": message.get("message_type") or "chat",
			"status": status,
			"task_type": message.get("task_type") or "",
			"component_id": message.get("component_id") or "",
			"metadata_json": json.dumps(meta_clean, separators=(",", ":")) if meta_clean else "",
		}
	).insert(ignore_permissions=True)

	# Preserve the legacy ordering — get_messages/build_context order by creation.
	created_at = message.get("created_at")
	if created_at:
		frappe.db.set_value("Studio AI Message", doc.name, "creation", created_at, update_modified=False)
