# Copyright (c) 2020, Frappe Technologies and contributors
# License: MIT. See LICENSE

from frappe.model.document import Document


class ModuleProfile(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.core.doctype.block_module.block_module import BlockModule
		from frappe.types import DF

		block_modules: DF.Table[BlockModule]
		module_profile_name: DF.Data
	# end: auto-generated types

	def onload(self):
		from frappe.utils.modules import get_modules_from_all_apps

		self.set_onload("all_modules", sorted(m.get("module_name") for m in get_modules_from_all_apps()))

	def get_permission_log_options(self, event=None):
		return {"fields": ["block_modules"]}
