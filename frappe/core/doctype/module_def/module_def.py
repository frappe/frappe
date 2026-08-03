# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

import json
import os
from pathlib import Path

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.modules.export_file import delete_folder


class ModuleDef(Document):
	_DOCTYPE_NAME = "Module Def"

	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		app_name: DF.Literal[None]
		custom: DF.Check
		module_name: DF.Data
		package: DF.Link | None
		restrict_to_domain: DF.Link | None
	# end: auto-generated types

	def validate(self):
		from frappe.modules.utils import get_module_app

		if not self.app_name and not self.custom:
			self.app_name = get_module_app(self.name)

	def on_update(self):
		"""If in `developer_mode`, create folder for module and
		add in `modules.txt` of app if missing."""
		frappe.clear_cache()
		if not self.custom and frappe.conf.get("developer_mode"):
			self.create_modules_folder()
			self.add_to_modules_txt()

	def after_insert(self):
		"""Every Module Def gets a `Module Sidebar`; the desk dock is 1:1 with this doctype."""
		from frappe.desk.doctype.module_sidebar.module_sidebar import sync_module_sidebars

		sync_module_sidebars(self.name)

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
			with open(frappe.get_app_path(self.app_name, "modules.txt")) as f:
				content = f.read()
				if self.name not in content.splitlines():
					modules = list(filter(None, content.splitlines()))
					modules.append(self.name)

			if modules:
				with open(frappe.get_app_path(self.app_name, "modules.txt"), "w") as f:
					f.write("\n".join(modules))

				frappe.clear_cache()
				frappe.setup_module_map()

	def on_trash(self):
		"""Delete module name from modules.txt"""
		# The sidebar is this module's content, so it goes with it. Unconditional -- the
		# developer_mode guard below is about editing modules.txt on disk, not about data.
		frappe.delete_doc("Module Sidebar", self.name, ignore_missing=True, force=True)

		if not frappe.conf.get("developer_mode") or frappe.flags.in_uninstall or self.custom:
			return

		if frappe.local.module_app.get(frappe.scrub(self.name)):
			frappe.db.after_commit.add(self.delete_module_from_file)

	def delete_module_from_file(self):
		try:
			delete_folder(self.module_name, "Module Def", self.name)
		except frappe.DoesNotExistError:
			# Runs after commit, so the Module Def row is already gone and the module may no
			# longer resolve to a path -- `delete_folder` re-reads it to choose between the
			# custom and app module paths. There is then nothing on disk to remove, and
			# raising here would abort whatever transaction happened to trigger the flush.
			# Fall through so modules.txt is still cleaned up.
			pass

		modules = []

		modules_txt = Path(frappe.get_app_path(self.app_name, "modules.txt"))
		modules = [m for m in modules_txt.read_text().splitlines() if m]

		if self.name in modules:
			modules.remove(self.name)

		if modules:
			modules_txt.write_text("\n".join(modules))
			frappe.clear_cache()
			frappe.setup_module_map()

	def before_rename(self, old, new, merge=False):
		if not self.custom:
			frappe.throw(_("Only Custom Modules can be renamed."))


@frappe.whitelist()
def get_installed_apps():
	return json.dumps(frappe.get_installed_apps())
