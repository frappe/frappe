# Copyright (c) 2020, Frappe Technologies and contributors
# License: MIT. See LICENSE

from frappe.model.document import Document


class ModuleProfile(Document):
	def onload(self):
		from frappe.config import get_modules_from_all_apps

		self.set_onload("all_modules", sorted(m.get("module_name") for m in get_modules_from_all_apps()))
