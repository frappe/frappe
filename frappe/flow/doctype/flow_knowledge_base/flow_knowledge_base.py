# Copyright (c) 2026, Frappe Technologies and contributors
# License: MIT. See LICENSE

import frappe
from frappe import _
from frappe.model.document import Document


class FlowKnowledgeBase(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		description: DF.SmallText | None
		enabled: DF.Check
		is_system_generated: DF.Check
		title: DF.Data
	# end: auto-generated types

	def validate(self):
		if self.is_new():
			from flow.flow.doctype.flow_knowledge_settings.flow_knowledge_settings import (
				require_embedding_model,
			)

			require_embedding_model()
		self._protect_system_generated_flag()

	def _protect_system_generated_flag(self):
		# Read the flag from the DB so unsetting it (which would bypass on_trash) is blocked.
		if self.is_new() or self.flags.ignore_permissions or self.is_system_generated:
			return
		if frappe.db.get_value("Flow Knowledge Base", self.name, "is_system_generated"):
			frappe.throw(
				_("Cannot remove the system-generated flag from knowledge base {0}.").format(self.name),
				title=_("Protected"),
			)

	def on_trash(self):
		if self.is_system_generated and not self.flags.ignore_permissions:
			frappe.throw(
				_("Cannot delete system-generated knowledge base {0}.").format(self.name),
				title=_("Protected"),
			)

	def before_rename(self, old: str, new: str, merge: bool = False) -> None:
		# Unconditional: the title is the app's sync identity; re-title via create + delete.
		if self.is_system_generated:
			frappe.throw(
				_("Cannot rename system-generated knowledge base {0}.").format(old),
				title=_("Protected"),
			)
