# Copyright (c) 2026, Frappe Technologies and contributors
# License: MIT. See LICENSE

from frappe.model.document import Document


class FlowKnowledgeChunk(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		chunk_index: DF.Int
		content: DF.LongText
		content_hash: DF.Data | None
		knowledge_base: DF.Link
		reference_doctype: DF.Link | None
		reference_name: DF.DynamicLink | None
		source: DF.Link
	# end: auto-generated types

	pass
