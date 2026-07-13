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

	def on_trash(self):
		# System-generated bases are owned by the app that shipped them; block Desk users
		# from deleting them while the owning app's sync (ignore_permissions) stays free.
		if self.is_system_generated and not self.flags.ignore_permissions:
			frappe.throw(
				_("Cannot delete system-generated knowledge base {0}.").format(self.name),
				title=_("Protected"),
			)

	def before_rename(self, old: str, new: str, merge: bool = False) -> None:
		if self.is_system_generated and not self.flags.ignore_permissions:
			frappe.throw(
				_("Cannot rename system-generated knowledge base {0}.").format(old),
				title=_("Protected"),
			)
