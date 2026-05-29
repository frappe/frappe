import json

import frappe


class AISession:
	DOCTYPE = "Studio AI Session"
	MAX_MESSAGES = 24

	def __init__(self, doc):
		self._doc = doc

	@classmethod
	def get_or_create(cls, page_id: str, model: str | None = None, user: str | None = None):
		user = user or frappe.session.user

		session_name = frappe.db.get_value(
			cls.DOCTYPE,
			{"page": page_id, "user": user},
			"name",
		)
		if session_name:
			doc = frappe.get_doc(cls.DOCTYPE, str(session_name))
			if model and not doc.selected_model:
				doc.selected_model = model
				doc.save(ignore_permissions=True)
			return cls(doc)

		doc = frappe.get_doc(
			{
				"doctype": cls.DOCTYPE,
				"page": page_id,
				"user": user,
				"selected_model": model or "",
				"messages_json": "[]",
				"last_interaction_on": frappe.utils.now_datetime(),
			}
		)
		doc.insert(ignore_permissions=True)
		return cls(doc)

	def get_messages(self) -> list[dict]:
		try:
			messages = json.loads(self._doc.messages_json or "[]")
		except json.JSONDecodeError:
			return []
		return messages if isinstance(messages, list) else []

	def _save_messages(self, messages: list[dict], task_type: str | None = None):
		trimmed = messages[-self.MAX_MESSAGES :]
		self._doc.messages_json = json.dumps(trimmed, separators=(",", ":"))
		self._doc.last_interaction_on = frappe.utils.now_datetime()
		if task_type:
			self._doc.last_task_type = task_type
		self._doc.save(ignore_permissions=True)

	def add_message(
		self,
		role: str,
		content: str,
		*,
		message_type: str = "chat",
		task_type: str | None = None,
		component_id: str | None = None,
		metadata: dict | None = None,
	):
		messages = self.get_messages()
		messages.append(
			{
				"id": frappe.generate_hash(length=10),
				"role": role,
				"content": content,
				"message_type": message_type,
				"task_type": task_type,
				"component_id": component_id,
				"created_at": str(frappe.utils.now_datetime()),
				"metadata": metadata or {},
			}
		)
		self._save_messages(messages, task_type=task_type)

	def build_context_string(self) -> str:
		history_lines = []
		for message in self.get_messages()[-10:]:
			role = message.get("role") or "user"
			content = (message.get("content") or "").strip()
			if not content:
				continue
			prefix = "User" if role == "user" else "Assistant"
			history_lines.append(f"{prefix}: {content}")

		if not history_lines:
			return ""
		return "Conversation history for this page:\n" + "\n".join(history_lines)

	def clear(self):
		self._doc.messages_json = "[]"
		self._doc.last_task_type = None
		self._doc.last_interaction_on = frappe.utils.now_datetime()
		self._doc.save(ignore_permissions=True)
