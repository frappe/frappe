# Copyright (c) 2026, Frappe Technologies Pvt Ltd and contributors
# For license information, please see license.txt

from __future__ import annotations

from frappe.model.document import Document


class StudioAIMessage(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		component_id: DF.Data | None
		content: DF.LongText | None
		message_type: DF.Literal["chat", "clarification", "status"]
		metadata_json: DF.LongText | None
		role: DF.Literal["user", "assistant"]
		session: DF.Link
		status: DF.Data | None
		task_type: DF.Data | None
	# end: auto-generated types
	pass
