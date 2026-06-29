import json

import frappe


def execute():
	"""Backfill legacy `Studio AI Session.messages_json` blobs into `Studio AI Message`
	rows. Leaves messages_json untouched so the old one-shot path keeps reading it."""
	sessions = frappe.get_all(
		"Studio AI Session",
		filters={"messages_json": ["is", "set"]},
		fields=["name", "messages_json"],
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
