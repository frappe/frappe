# Copyright (c) 2024, Frappe Technologies Pvt Ltd and contributors
# For license information, please see license.txt
import frappe
from frappe import _
from frappe.model.document import Document

from studio.utils import camel_case_to_kebab_case


class StudioPage(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		from studio.studio.doctype.studio_page_client_script.studio_page_client_script import (
			StudioPageClientScript,
		)
		from studio.studio.doctype.studio_page_resource.studio_page_resource import StudioPageResource
		from studio.studio.doctype.studio_page_variable.studio_page_variable import StudioPageVariable
		from studio.studio.doctype.studio_page_watcher.studio_page_watcher import StudioPageWatcher

		blocks: DF.JSON | None
		client_scripts: DF.TableMultiSelect[StudioPageClientScript]
		draft_blocks: DF.JSON | None
		page_name: DF.Data | None
		page_title: DF.Data | None
		published: DF.Check
		resources: DF.TableMultiSelect[StudioPageResource]
		route: DF.Data | None
		studio_app: DF.Link | None
		variables: DF.Table[StudioPageVariable]
		watchers: DF.Table[StudioPageWatcher]
	# end: auto-generated types

	def autoname(self):
		if not self.name:
			self.name = f"page-{frappe.generate_hash(length=8)}"

	def before_insert(self):
		if isinstance(self.blocks, list):
			self.blocks = frappe.as_json(self.blocks, indent=None)
		if isinstance(self.draft_blocks, list):
			self.draft_blocks = frappe.as_json(self.draft_blocks, indent=None)
		if not self.blocks:
			self.blocks = "[]"
		if not self.page_title:
			self.page_title = "My Page"
		if not self.route:
			self.route = f"{camel_case_to_kebab_case(self.page_title, True)}-{frappe.generate_hash(length=4)}"

	def after_insert(self):
		app_home = frappe.db.get_value("Studio App", self.studio_app, "app_home")
		if not app_home:
			frappe.db.set_value("Studio App", self.studio_app, "app_home", self.name)

	def validate(self):
		# vue router needs a leading slash
		if not self.route.startswith("/"):
			self.route = f"/{self.route}"

		self.validate_variables()

	def validate_variables(self):
		# check for duplicate variable names and show the duplicate variable name
		variable_names = [variable.variable_name for variable in self.variables]
		duplicate_variable_names = set(x for x in variable_names if variable_names.count(x) > 1)
		if duplicate_variable_names:
			frappe.throw(_("Duplicate variable name: {0}").format(", ".join(duplicate_variable_names)))

	@frappe.whitelist()
	def publish(self, **kwargs):
		frappe.form_dict.update(kwargs)
		self.published = 1
		if self.draft_blocks:
			self.blocks = self.draft_blocks
			self.draft_blocks = None
		self.save()


@frappe.whitelist()
def find_page_with_route(app_name: str, page_route: str) -> str | None:
	if not page_route.startswith("/"):
		page_route = f"/{page_route}"
	try:
		return frappe.db.get_value(
			"Studio Page", dict(studio_app=app_name, route=page_route, published=1), "name", cache=True
		)
	except frappe.DoesNotExistError:
		pass


@frappe.whitelist()
def duplicate_page(page_name: str, app_name: str | None):
	if not frappe.has_permission("Studio Page", ptype="write"):
		frappe.throw("You do not have permission to duplicate a page.")

	page = frappe.get_doc("Studio Page", page_name)
	new_page = frappe.copy_doc(page)
	del new_page.page_name
	new_page.page_title = f"{new_page.page_title} Copy"
	new_page.route = None
	new_page.studio_app = app_name
	new_page.insert()

	return new_page
