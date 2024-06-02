# Copyright (c) 2024, Frappe Technologies and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.modules.export_file import delete_folder, export_to_files


class DesktopItem(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		color: DF.Color | None
		custom: DF.Check
		label: DF.Data
		link_type: DF.Literal["Module", "URL"]
		module: DF.Link | None
		url: DF.Data | None
	# end: auto-generated types

	def on_update(self):
		if frappe.conf.developer_mode and not self.custom:
			if self.module:
				export_to_files(record_list=[["Desktop Item", self.name]], record_module=self.module)

			if self.has_value_changed("label") or self.has_value_changed("module"):
				previous = self.get_doc_before_save()
				if previous and previous.get("module") and previous.get("label"):
					delete_folder(previous.get("module"), "Desktop Item", previous.get("label"))

	def after_delete(self):
		if frappe.conf.developer_mode and self.module and not self.custom:
			delete_folder(self.module, "Desktop Item", self.label)
