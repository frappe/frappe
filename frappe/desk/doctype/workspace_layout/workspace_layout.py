# Copyright (c) 2026, Frappe Technologies and contributors
# For license information, please see license.txt

import os

import frappe
from frappe import _
from frappe.desk.layouts import clear_caches
from frappe.model.document import Document
from frappe.modules import get_module_path, scrub
from frappe.modules.export_file import strip_default_fields


class WorkspaceLayout(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		changes: DF.JSON | None
		condition: DF.Code | None
		layout_name: DF.Data | None
		module: DF.Link | None
		user: DF.Link | None
		workspace: DF.Link
	# end: auto-generated types

	def autoname(self):
		# an app's layout is named the same on every site, so its file finds it
		if self.module:
			self.name = f"{self.module}-{self.workspace}-{self.layout_name}"

	def validate(self):
		if self.module and not self.layout_name:
			frappe.throw(_("An app's layout needs a name."), title=_("Layout Name"))
		if self.user and (self.module or self.condition):
			frappe.throw(_("A person's own layout always applies to them and belongs to no app."))
		self.validate_condition()

	def validate_condition(self):
		if not self.condition:
			return
		try:
			compile(self.condition, "<condition>", "eval")
		except SyntaxError as e:
			frappe.throw(_("Show When is not a Python expression: {0}").format(e.msg), title=_("Show When"))

	def on_update(self):
		clear_caches(self.workspace, self.user)
		if self.is_exported():
			self.export()

	def on_trash(self):
		clear_caches(self.workspace, self.user)
		if self.is_exported() and os.path.exists(path := self.file_path()):
			os.remove(path)

	def is_exported(self) -> bool:
		return bool(
			frappe.conf.developer_mode
			and self.module
			and not frappe.flags.in_import
			and not frappe.db.get_value("Module Def", self.module, "custom")
		)

	def file_path(self) -> str:
		folder = os.path.join(get_module_path(self.module), "workspace", scrub(self.workspace), "layouts")
		return os.path.join(folder, f"{scrub(self.layout_name)}.json")

	def export(self):
		path = self.file_path()
		frappe.create_folder(os.path.dirname(path))
		with open(path, "w") as f:  # nosemgrep
			f.write(frappe.as_json(strip_default_fields(self, self.as_dict(no_nulls=True))) + "\n")


def remove_layouts_without_files(app: str):
	"""An app's folder is the whole truth about its layouts: one whose file is gone goes too."""
	modules = frappe.get_all("Module Def", filters={"app_name": app}, pluck="name")
	layouts = frappe.get_all("Workspace Layout", filters={"module": ("in", modules)}, pluck="name")
	for name in layouts:
		layout = frappe.get_doc("Workspace Layout", name)
		if not os.path.exists(layout.file_path()):
			frappe.delete_doc("Workspace Layout", name, ignore_permissions=True)
