# Copyright (c) 2026, Frappe Technologies and contributors
# For license information, please see license.txt

import os

import frappe
from frappe import _
from frappe.desk.layouts import clear_caches
from frappe.model.document import Document
from frappe.modules import get_module_path, scrub
from frappe.modules.export_file import exports_to_app, write_record

# about thirty times the largest layout an app ships, so a person's own layouts stay bounded
USER_LAYOUT_MAX_LENGTH = 100_000


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

	def before_validate(self):
		from frappe.desk.doctype.workspace.workspace import sanitize_content

		# a layout carries headings and paragraphs the page draws as HTML, as a workspace's own do
		self.changes = sanitize_content(frappe.as_json(frappe.parse_json(self.changes or "{}"), indent=None))

	def validate(self):
		self.validate_owner()
		if self.module and not self.layout_name:
			frappe.throw(_("An app's layout needs a name."), title=_("Layout Name"))
		if self.user and (self.module or self.condition):
			frappe.throw(_("A person's own layout always applies to them and belongs to no app."))
		self.validate_condition()
		self.validate_name_is_free()
		if (
			self.user
			and len(frappe.as_json(frappe.parse_json(self.changes or "{}"))) > USER_LAYOUT_MAX_LENGTH
		):
			frappe.throw(_("This layout is too large to save. Remove some blocks and try again."))

	def validate_owner(self):
		"""Anyone may keep a layout of their own. The site's are a Workspace Manager's, and an app's
		come from its files or a developer."""
		from frappe.desk.doctype.workspace.workspace import is_workspace_manager

		if frappe.flags.in_import or frappe.flags.in_patch or frappe.flags.in_install:
			return
		if self.module and not frappe.conf.developer_mode:
			frappe.throw(_("An app's layout can be changed only in developer mode."), frappe.PermissionError)
		if self.user and self.user != frappe.session.user:
			frappe.throw(_("A layout of your own can only be yours."), frappe.PermissionError)
		if not self.user and not is_workspace_manager():
			frappe.throw(
				_("You need to be Workspace Manager to change the site's layouts."), frappe.PermissionError
			)

	def validate_name_is_free(self):
		"""A layout's name picks it out among the layouts its app, or the site, ships for a page."""
		if not self.layout_name or self.user:
			return
		taken = frappe.db.exists(
			"Workspace Layout",
			{
				"workspace": self.workspace,
				"layout_name": self.layout_name,
				"module": self.module or ("is", "not set"),
				"user": ("is", "not set"),
				"name": ("!=", self.name or ""),
			},
		)
		if taken:
			frappe.throw(_("This page already has a layout named {0}.").format(frappe.bold(self.layout_name)))

	def validate_condition(self):
		if not self.condition:
			return
		try:
			compile(self.condition, "<condition>", "eval")
		except SyntaxError as e:
			frappe.throw(_("Show When is not a Python expression: {0}").format(e.msg), title=_("Show When"))

	def on_update(self):
		# a person's own layout has no condition, so everyone else's condition results still hold
		clear_caches(self.workspace, self.user, conditions=not self.user)
		if self.is_exported():
			self.export()

	def on_trash(self):
		clear_caches(self.workspace, self.user)
		if self.is_exported() and os.path.exists(path := self.file_path()):
			os.remove(path)

	def is_exported(self) -> bool:
		return exports_to_app(self.module)

	def file_path(self) -> str:
		return layout_file(self.module, self.workspace, self.layout_name)

	def export(self):
		write_record(self, self.file_path())


def remove_layouts_without_files(app: str):
	"""An app's folder is the whole truth about its layouts: one whose file is gone goes too."""
	modules = frappe.get_all("Module Def", filters={"app_name": app}, pluck="name")
	fields = ["name", "module", "workspace", "layout_name"]
	for layout in frappe.get_all("Workspace Layout", filters={"module": ("in", modules)}, fields=fields):
		if not os.path.exists(layout_file(layout.module, layout.workspace, layout.layout_name)):
			frappe.delete_doc("Workspace Layout", layout.name, ignore_permissions=True)


def layout_file(module: str, workspace: str, layout_name: str) -> str:
	folder = os.path.join(get_module_path(module), "workspace", scrub(workspace), "layouts")
	return os.path.join(folder, f"{scrub(layout_name)}.json")


def has_permission(doc, ptype="read", user=None, debug=False):
	"""One person's own layout is theirs alone, whatever roles the reader holds."""
	return not doc.user or doc.user == (user or frappe.session.user)


def get_permission_query_conditions(user=None):
	"""Keep other people's own layouts out of list reads."""
	user = user or frappe.session.user
	return f"(ifnull(`tabWorkspace Layout`.`user`, '') = '' or `tabWorkspace Layout`.`user` = {frappe.db.escape(user)})"
