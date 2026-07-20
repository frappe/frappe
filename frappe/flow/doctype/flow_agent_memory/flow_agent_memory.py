# Copyright (c) 2026, Frappe Technologies and contributors
# License: MIT. See LICENSE

from __future__ import annotations

import frappe
from frappe import _
from frappe.model.document import Document

MAX_CONTENT_CHARS = 500


class FlowAgentMemory(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		agent: DF.Link
		content: DF.SmallText
		keywords: DF.SmallText | None
		scope: DF.Literal["Agent", "User"]
		source: DF.Literal["Agent", "Feedback", "Manual"]
		source_run: DF.Link | None
		status: DF.Literal["Active", "Archived"]
		user: DF.Link | None
	# end: auto-generated types

	def validate(self):
		self.content = (self.content or "").strip()
		if not self.content:
			frappe.throw(_("Memory content is required."), title=_("Empty Memory"))
		if len(self.content) > MAX_CONTENT_CHARS:
			frappe.throw(
				_("Keep each memory under {0} characters — split or shorten it.").format(MAX_CONTENT_CHARS),
				title=_("Memory Too Long"),
			)
		if self.scope == "User" and not self.user:
			frappe.throw(_("User-scoped memories must have a user."), title=_("Missing User"))
		if self.scope == "Agent":
			self.user = None

	def on_update(self):
		from flow.memory import store

		store.sync(self)

	def on_trash(self):
		from flow.memory import store

		store.remove(self.name)
