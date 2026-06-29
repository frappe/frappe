# Copyright (c) 2026, Frappe Technologies and contributors
# License: MIT. See LICENSE

from frappe.model.document import Document


class FlowKnowledgeBase(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		description: DF.SmallText | None
		enabled: DF.Check
		title: DF.Data
	# end: auto-generated types

	def validate(self):
		if self.is_new():
			from flow.flow.doctype.flow_knowledge_settings.flow_knowledge_settings import (
				require_embedding_model,
			)

			require_embedding_model()
