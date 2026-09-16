# Copyright (c) 2026, Frappe Technologies and contributors
# License: MIT. See LICENSE

from frappe.model.document import Document

from flow.utils.system_generated import block_delete, block_rename, validate_immutable


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
		validate_immutable(self)

	def on_trash(self):
		block_delete(self)

	def before_rename(self, old: str, new: str, merge: bool = False) -> None:
		block_rename(self, old)
