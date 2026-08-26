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
		self.validate_placement()

	def validate_placement(self):
		"""Validate `app_name`, which says which dock lists this module and nothing else.

		It used to answer two unrelated questions, placement and ownership, so leaving it empty
		made a module unreachable and filling it in let an app's uninstall destroy a module the
		site had built. Ownership is now decided by `custom` alone (see
		`frappe.installer.get_app_owned_modules`), which lets placement be optional:

		        app_name set     -> listed in that app's dock, after the app's own modules
		        app_name null    -> unplaced; the module stands on its own
		        host uninstalled -> cleared, so the module can never become unreachable

		An app's own module still resolves its app from `modules.txt`, which is where the app
		declares what it ships.
		"""
		if self.custom:
			# Skip during install: the app being installed is not in `installed_apps` until its
			# install finishes, so a placement into it is early rather than stale.
			if self.app_name and not frappe.flags.in_install:
				if self.app_name not in frappe.get_installed_apps():
					# The app that would have listed it is gone but the module is not. Uninstall
					# clears this too; doing it here as well means a placement never outlives its
					# host.
					self.app_name = None
			return

		if not self.app_name:
			from frappe.modules.utils import get_module_app

			self.app_name = get_module_app(self.name)

	def after_insert(self):
		"""Create the page a site-added module opens on.

		This is required, not cosmetic: a module whose sidebar comes out empty is dropped from the
		payload entirely (`resolve_sidebar`), so it is absent from `module_sidebars`, no dock entry
		naming it resolves, and no desktop tile stands for it. A custom module created with nothing
		in it would be unreachable.

		It applies only to the site's own modules. An app's modules arrive with whatever the app
		ships, and creating a page for each of them at install would invent content on the app's
		behalf.

		It also applies only when a user adds a module. Install, migrate and patches create modules
		to describe things that already exist, such as `backfill_workspace_module` creating one for
		an existing workspace, so a page created then would be content nobody asked for under a
		name someone else picked.
		"""
		from frappe.desk.doctype.workspace.workspace import make_module_workspace

		if not self.custom:
			return
		if frappe.flags.in_install or frappe.flags.in_migrate or frappe.flags.in_patch:
			return
		if frappe.flags.in_import or frappe.flags.in_fixtures:
			return

		# `page_icon` is how a caller says what the module looks like. The icon lands on the page
		# the module opens on, which is where a computed sidebar reads a module's header icon from.
		# It is a flag rather than a field, because a module has no icon of its own; its page does.
		make_module_workspace(self.name, icon=self.flags.page_icon)

	def on_update(self):
		"""If in `developer_mode`, create folder for module and
		add in `modules.txt` of app if missing."""
		frappe.clear_cache()
		if not self.custom and frappe.conf.get("developer_mode"):
			self.create_modules_folder()
			self.add_to_modules_txt()

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
		# The sidebars are this module's content, so they go with it. All of them, not just the one
		# named after the module: a sidebar is named by its title now, so a module may own several
		# and deleting by name would leave the rest pointing at a module that is gone. This is
		# unconditional; the developer_mode guard below is about editing modules.txt on disk, not
		# about data.
		for name in frappe.get_all("Sidebar", filters={"module": self.name}, pluck="name"):
			frappe.delete_doc("Sidebar", name, ignore_missing=True, force=True)

		# The site's and every user's customizations go too, since they are anchored to the module
		# rather than to the sidebar document. Navigation links are in `ignore_links_on_delete`, so
		# no Link refuses this delete on a customization's behalf, and refusing was never right for
		# a module going away.
		for name in frappe.get_all("Custom Sidebar", filters={"module": self.name}, pluck="name"):
			frappe.delete_doc("Custom Sidebar", name, ignore_permissions=True, force=True)

		if not frappe.conf.get("developer_mode") or frappe.flags.in_uninstall or self.custom:
			return

		if frappe.local.module_app.get(frappe.scrub(self.name)):
			frappe.db.after_commit.add(self.delete_module_from_file)

	def delete_module_from_file(self):
		try:
			delete_folder(self.module_name, "Module Def", self.name)
		except frappe.DoesNotExistError:
			# Runs after commit, so the Module Def row is already gone and the module may no
			# longer resolve to a path, and `delete_folder` re-reads it to choose between the
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
