# Copyright (c) 2026, Frappe Technologies and contributors
# License: MIT. See LICENSE

import frappe
from frappe import _
from frappe.flow.utils.system_generated import block_delete, block_rename, validate_immutable
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
			from frappe.flow.doctype.flow_knowledge_settings.flow_knowledge_settings import (
				require_embedding_model,
			)

			require_embedding_model()
		validate_immutable(self)

	def on_trash(self):
		block_delete(self)

	def before_rename(self, old: str, new: str, merge: bool = False) -> None:
		block_rename(self, old)
		# a running ingestion saves its chunks under the old name
		if frappe.db.exists("Flow Knowledge Source", {"knowledge_base": old, "status": "Processing"}):
			frappe.throw(
				_("{0} has sources still processing. Rename it once they finish.").format(old),
				title=_("Sources Processing"),
			)

	def after_rename(self, old: str, new: str, merge: bool = False) -> None:
		from frappe.flow.knowledge import store

		store.rename_kb(old, new)
