# Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals
import frappe, os

from frappe.model.document import Document

class ModuleDef(Document):
	def validate(self):
		if not frappe.conf.get("developer_mode"):
			return

		modules = None
		if not frappe.local.module_app.get(frappe.scrub(self.name)):
			with open(frappe.get_app_path(self.app_name, "modules.txt"), "r") as f:
				content = f.read()
				if not self.name in content.splitlines():
					modules = filter(None, content.splitlines())
					modules.append(self.name)

			if modules:
				with open(frappe.get_app_path(self.app_name, "modules.txt"), "w") as f:
					f.write("\n".join(modules))

				frappe.clear_cache()
				frappe.setup_module_map()

		module_path = frappe.get_app_path(self.app_name, self.name)
		if not os.path.exists(module_path):
			os.mkdir(module_path)
			with open(os.path.join(module_path, "__init__.py"), "w") as f:
				f.write("")



