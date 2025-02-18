# Copyright (c) 2024, Frappe Technologies Pvt Ltd and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document

from studio.utils import camel_case_to_kebab_case


class StudioApp(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		app_home: DF.Link | None
		app_name: DF.Data | None
		app_title: DF.Data | None
		route: DF.Data | None
	# end: auto-generated types

	def autoname(self):
		if not self.name:
			self.name = f"app-{frappe.generate_hash(length=8)}"

	def before_insert(self):
		if not self.app_title:
			self.app_title = "My App"
		if not self.route:
			self.route = f"studio-app/{camel_case_to_kebab_case(self.app_title, True)}-{frappe.generate_hash(length=4)}"

	def validate(self):
		self.set_app_home()

	def set_app_home(self):
		if self.app_home:
			return

		if self.pages:
			self.app_home = self.pages[0].studio_page


@frappe.whitelist()
def get_app_pages(app_route: str) -> list[dict]:
	app_name = frappe.db.get_value("Studio App", dict(route=f"studio-app/{app_route}"), "name")

	StudioAppPage = frappe.qb.DocType("Studio App Page")
	StudioPage = frappe.qb.DocType("Studio Page")
	return (
		frappe.qb.from_(StudioAppPage)
		.inner_join(StudioPage)
		.on(StudioAppPage.studio_page == StudioPage.name)
		.select(StudioPage.name, StudioPage.page_title, StudioPage.route)
		.where(StudioAppPage.parent == app_name)
	).run(as_dict=True)
