import json

import frappe
from frappe import _


class AISession:
	DOCTYPE = "Studio AI Session"
	MESSAGE_DOCTYPE = "Studio AI Message"
	CONTEXT_WINDOW = 10  # how many prior turns to feed back to the model

	def __init__(self, doc):
		self._doc = doc

	# --- factories --------------------------------------------------------

	@classmethod
	def get_or_create(cls, page_id: str, model: str | None = None, user: str | None = None):
		user = user or frappe.session.user

		session_name = frappe.db.get_value(
			cls.DOCTYPE,
			{"page": page_id, "user": user, "status": "Active"},
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
				"status": "Active",
				"selected_model": model or "",
				"last_interaction_on": frappe.utils.now_datetime(),
			}
		)
		doc.insert(ignore_permissions=True)
		return cls(doc)

	@classmethod
	def get(cls, session_id: str, page_id: str | None = None, user: str | None = None):
		user = user or frappe.session.user
		if not frappe.db.exists(cls.DOCTYPE, session_id):
			frappe.throw(_("AI session not found"))
		doc = frappe.get_doc(cls.DOCTYPE, session_id)
		if doc.user != user:
			frappe.throw(_("You do not have access to this AI session"))
		if page_id and doc.page != page_id:
			frappe.throw(_("AI session does not belong to this page"))
		return cls(doc)

	@classmethod
	def try_append_message(cls, session_id: str | None, role: str, content: str, **kwargs):
		if session_id and frappe.db.exists(cls.DOCTYPE, session_id):
			cls(frappe.get_doc(cls.DOCTYPE, session_id)).append_message(role, content, **kwargs)

	@classmethod
	def build_context_messages_from_id(cls, session_id: str | None) -> list[dict]:
		if not session_id or not frappe.db.exists(cls.DOCTYPE, session_id):
			return []
		return cls(frappe.get_doc(cls.DOCTYPE, session_id)).build_context_messages()

	# --- properties -------------------------------------------------------

	@property
	def name(self):
		return self._doc.name

	@property
	def page(self):
		return self._doc.page

	@property
	def selected_model(self):
		return self._doc.selected_model

	@property
	def last_task_type(self):
		return self._doc.last_task_type

	# --- message read -----------------------------------------------------

	@staticmethod
	def _row_to_message(row: dict) -> dict:
		"""Reshape a Studio AI Message DB row into the ChatMessage dict shape the
		frontend renders."""
		try:
			metadata = json.loads(row.get("metadata_json") or "{}") or {}
		except (json.JSONDecodeError, TypeError):
			metadata = {}
		# `status` lives in its own column for queryability; surface it in the
		# returned metadata dict so callers see the same shape as before.
		if row.get("status"):
			metadata["status"] = row["status"]
		return {
			"id": row.get("name"),
			"role": row.get("role"),
			"content": row.get("content") or "",
			"message_type": row.get("message_type"),
			"task_type": row.get("task_type") or None,
			"component_id": row.get("component_id") or None,
			"created_at": str(row.get("creation")) if row.get("creation") else None,
			"metadata": metadata,
		}

	_FIELDS = (
		"name",
		"role",
		"content",
		"message_type",
		"task_type",
		"component_id",
		"status",
		"metadata_json",
		"creation",
	)

	def get_messages(self) -> list[dict]:
		"""Return ALL messages for this session in chronological order, shaped for
		the frontend's ChatMessage interface."""
		rows = frappe.db.get_all(
			self.MESSAGE_DOCTYPE,
			filters={"session": self._doc.name},
			fields=list(self._FIELDS),
			order_by="creation asc",
			limit_page_length=0,
		)
		return [self._row_to_message(r) for r in rows]

	def build_context_messages(self) -> list[dict]:
		"""Return the last N prior turns as proper role-tagged messages.

		Excludes the current-turn user message (the caller appends a fresh one),
		and filters out transient status/error/cancelled chatter."""
		# Fetch one extra (the current user message) and drop it.
		rows = frappe.db.get_all(
			self.MESSAGE_DOCTYPE,
			filters={"session": self._doc.name},
			fields=["role", "content", "message_type", "status", "metadata_json"],
			order_by="creation desc",
			limit_page_length=self.CONTEXT_WINDOW + 1,
		)
		# Skip the most recent row (current user msg) and reverse to chrono order.
		history = list(reversed(rows[1:])) if rows else []
		out: list[dict] = []
		for r in history:
			content = (r.get("content") or "").strip()
			role = r.get("role")
			if not content or role not in ("user", "assistant"):
				continue
			if r.get("message_type") == "status":
				continue
			if r.get("status") in ("running", "error", "cancelled"):
				continue
			out.append({"role": role, "content": content})
		return out

	# --- message write ----------------------------------------------------

	def append_message(
		self,
		role: str,
		content: str,
		*,
		message_type: str = "chat",
		task_type: str | None = None,
		component_id: str | None = None,
		metadata: dict | None = None,
	):
		metadata = metadata or {}
		# Hoist status to its own column for cheap filtered queries; keep
		# everything else in metadata_json.
		status = ""
		meta_clean: dict = {}
		if isinstance(metadata, dict):
			status = (metadata.get("status") or "").strip()
			meta_clean = {k: v for k, v in metadata.items() if k != "status"}

		frappe.get_doc(
			{
				"doctype": self.MESSAGE_DOCTYPE,
				"session": self._doc.name,
				"role": role,
				"content": content,
				"message_type": message_type,
				"status": status,
				"task_type": task_type or "",
				"component_id": component_id or "",
				"metadata_json": json.dumps(meta_clean, separators=(",", ":")) if meta_clean else "",
			}
		).insert(ignore_permissions=True)

		# Touch the parent's bookkeeping fields atomically (no full re-save).
		updates: dict = {"last_interaction_on": frappe.utils.now_datetime()}
		if task_type:
			updates["last_task_type"] = task_type
		frappe.db.set_value(self.DOCTYPE, self._doc.name, updates, update_modified=False)

	def update_last_assistant_metadata(self, extra_metadata: dict):
		"""Merge extra_metadata into the most recent assistant message's
		metadata_json. One-row UPDATE — no read-modify-write of a giant blob."""
		row = frappe.db.get_value(
			self.MESSAGE_DOCTYPE,
			{"session": self._doc.name, "role": "assistant"},
			["name", "metadata_json"],
			order_by="creation desc",
			as_dict=True,
		)
		if not row:
			return
		try:
			meta = json.loads(row.metadata_json) if row.metadata_json else {}
		except (json.JSONDecodeError, TypeError):
			meta = {}
		if not isinstance(meta, dict):
			meta = {}
		meta.update(extra_metadata or {})
		frappe.db.set_value(
			self.MESSAGE_DOCTYPE,
			row.name,
			"metadata_json",
			json.dumps(meta, separators=(",", ":")),
			update_modified=False,
		)

	# --- running flag (concurrency guard) --------------------------------

	def set_running(self):
		frappe.db.set_value(self.DOCTYPE, self._doc.name, "is_running", 1, update_modified=False)
		frappe.db.commit()

	def clear_running(self):
		frappe.db.set_value(self.DOCTYPE, self._doc.name, "is_running", 0, update_modified=False)
		frappe.db.commit()

	@classmethod
	def is_session_running(cls, session_id: str) -> bool:
		if not session_id or not frappe.db.exists(cls.DOCTYPE, session_id):
			return False
		return bool(frappe.db.get_value(cls.DOCTYPE, session_id, "is_running"))

	# --- lifecycle --------------------------------------------------------

	def truncate_from_turn(self, message_id: str):
		"""Delete the turn that produced `message_id` and everything after it: the
		assistant message, its triggering user prompt, and all later messages. Used by
		the chat "revert" action to rewind the conversation alongside the page."""
		target = frappe.db.get_value(
			self.MESSAGE_DOCTYPE, {"name": message_id, "session": self._doc.name}, "creation"
		)
		if not target:
			return
		# The prompt that started this turn is the most recent user message at/before
		# the assistant reply; deleting from there removes the whole exchange.
		user_creation = frappe.db.get_value(
			self.MESSAGE_DOCTYPE,
			{"session": self._doc.name, "role": "user", "creation": ["<=", target]},
			"creation",
			order_by="creation desc",
		)
		cutoff = user_creation or target
		frappe.db.delete(self.MESSAGE_DOCTYPE, {"session": self._doc.name, "creation": [">=", cutoff]})
		frappe.db.set_value(self.DOCTYPE, self._doc.name, "is_running", 0, update_modified=False)
		frappe.db.commit()

	def clear(self):
		"""Wipe all messages for this session and reset transient state."""
		frappe.db.delete(self.MESSAGE_DOCTYPE, {"session": self._doc.name})
		frappe.db.set_value(
			self.DOCTYPE,
			self._doc.name,
			{
				"is_running": 0,
				"last_task_type": None,
				"last_interaction_on": frappe.utils.now_datetime(),
			},
			update_modified=False,
		)
		frappe.db.commit()
