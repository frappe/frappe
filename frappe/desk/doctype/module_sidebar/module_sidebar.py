# Copyright (c) 2024, Frappe Technologies and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.modules.export_file import delete_folder, export_to_files


class ModuleSidebar(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.desk.doctype.module_sidebar_item.module_sidebar_item import ModuleSidebarItem
		from frappe.desk.doctype.module_sidebar_workspace.module_sidebar_workspace import (
			ModuleSidebarWorkspace,
		)
		from frappe.types import DF

		custom: DF.Check
		for_user: DF.Link | None
		items: DF.Table[ModuleSidebarItem]
		module: DF.Link
		workspaces: DF.Table[ModuleSidebarWorkspace]
	# end: auto-generated types

	def on_update(self):
		if frappe.conf.developer_mode and not self.custom:
			export_to_files(record_list=[["Module Sidebar", self.name]], record_module=self.module)

			if self.has_value_changed("module"):
				previous = self.get_doc_before_save()
				if previous and previous.get("module") and previous.get("label"):
					delete_folder(previous.get("module"), "Module Sidebar", previous.get("label"))

	def after_delete(self):
		if frappe.conf.developer_mode and self.module and not self.custom:
			delete_folder(self.module, "Module Sidebar", self.label)
