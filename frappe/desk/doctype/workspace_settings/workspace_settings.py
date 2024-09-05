# Copyright (c) 2024, Frappe Technologies and contributors
# For license information, please see license.txt

import json

import frappe
from frappe.model.document import Document


class WorkspaceSettings(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		workspace_setup_completed: DF.Check
		workspace_visibility_json: DF.JSON
	# end: auto-generated types

	pass

	def validate(self):
		cnt = 1
		for page_name in json.loads(self.workspace_sequence):
			frappe.db.set_value("Workspace", page_name, "sequence_id", cnt)
			cnt += 1

	def on_update(self):
		frappe.clear_cache()
