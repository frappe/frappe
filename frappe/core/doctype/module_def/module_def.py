# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals
import frappe, os

from frappe.model.document import Document

class ModuleDef(Document):
	def on_update(self):
		"""If in `developer_mode`, create folder for module and
			add in `modules.txt` of app if missing."""
		frappe.clear_cache()
		if frappe.conf.get("developer_mode"):
			self.create_modules_folder()
			self.add_to_modules_txt()
			self.update_create_on_install_for_doctypes()

	def create_modules_folder(self):
		"""Creates a folder `[app]/[module]` and adds `__init__.py`"""
		module_path = frappe.get_app_path(self.app_name, self.name)
		if not os.path.exists(module_path):
			os.mkdir(module_path)
			with open(os.path.join(module_path, "__init__.py"), "w") as f:
				f.write("")

	def add_to_modules_txt(self):
		"""Adds to `[app]/modules.txt`"""
		modules = None
		if not frappe.local.module_app.get(frappe.scrub(self.name)):
			with open(frappe.get_app_path(self.app_name, "modules.txt"), "r") as f:
				content = f.read()
				if not self.name in content.splitlines():
					modules = list(filter(None, content.splitlines()))
					modules.append(self.name)

			if modules:
				with open(frappe.get_app_path(self.app_name, "modules.txt"), "w") as f:
					f.write("\n".join(modules))

				frappe.clear_cache()
				frappe.setup_module_map()

	def update_create_on_install_for_doctypes(self):
		if frappe.flags.in_install:
			return

		doc = self.get_doc_before_save()
		if not self.create_on_install == doc.create_on_install:
			for dt in frappe.get_list("DocType", filters={"module": self.name}):
				d = frappe.get_doc("DocType", dt.name)
				d.create_on_install = self.create_on_install
				d.save()

@frappe.whitelist()
def enable_module(module):
	"""
		Enables Module by initializing the tables in db
	"""
	from frappe.core.doctype.doctype.doctype import create_table

	if frappe.db.get_value("Module Def", module, "enabled"):
		return

	log_enabled_module(module)

	if frappe.conf.developer_mode and module == "Developer":
		return

	for doctype in frappe.get_list("DocType", filters={"module": module}):
		create_table(doctype.name)

	return get_enabled_modules()

def get_disabled_modules_from_tables(tables):
	modules = []
	for table in tables:
		module = frappe.get_meta(table).module
		if not frappe.db.get_value("Module Def", module, "enabled"):
			modules.append(module)

	return list(set(modules))

def log_enabled_module(module):
	if not "tabModule Def" in frappe.db.get_tables():
		return

	if frappe.db.exists("Module Def", module) or frappe.conf.developer_mode:
		frappe.db.set_value("Module Def", module, "enabled", 1)

		if not frappe.cache().hget("modules", "enabled"):
			frappe.cache().hset("modules", "enabled", [])

		frappe.cache().hget("modules", "enabled").append(module)

@frappe.whitelist()
def get_enabled_modules():
	if not "tabModule Def" in frappe.db.get_tables():
		return []

	return [d.name for d in frappe.get_list("Module Def", filters={"enabled": 1})]