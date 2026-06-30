# Copyright (c) 2026, Frappe Technologies Pvt Ltd and contributors
# For license information, please see license.txt
import frappe
from frappe.model.document import Document


class StudioAISession(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		is_running: DF.Check
		last_interaction_on: DF.Datetime | None
		last_task_type: DF.Data | None
		messages_json: DF.LongText | None
		page: DF.Link
		selected_model: DF.Data | None
		status: DF.Literal["Active", "Archived"]
		user: DF.Link

	# end: auto-generated types

	def on_trash(self):
		self.delete_ai_messages()

	def delete_ai_messages(self):
		for message in frappe.get_all("Studio AI Message", filters={"session": self.name}, pluck="name"):
			frappe.delete_doc("Studio AI Message", message, ignore_missing=True)
