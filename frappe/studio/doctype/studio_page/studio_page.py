# Copyright (c) 2024, Frappe Technologies Pvt Ltd and contributors
# For license information, please see license.txt
import frappe
from frappe.model.document import Document

from studio.utils import camel_case_to_kebab_case


class StudioPage(Document):
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

	@frappe.whitelist()
	def publish(self, **kwargs):
		frappe.form_dict.update(kwargs)
		self.published = 1
		if self.draft_blocks:
			self.blocks = self.draft_blocks
			self.draft_blocks = None
		self.save()


@frappe.whitelist()
def find_page_with_route(route: str) -> str | None:
	try:
		return frappe.db.get_value("Studio Page", dict(route=route, published=1), "name", cache=True)
	except frappe.DoesNotExistError:
		pass


@frappe.whitelist()
def duplicate_page(page_name: str, app_name: str | None):
	if not frappe.has_permission("Studio Page", ptype="write"):
		frappe.throw("You do not have permission to duplicate a page.")

	page = frappe.get_doc("Studio Page", page_name)
	new_page = frappe.copy_doc(page)
	del new_page.page_name
	new_page.route = None
	new_page.studio_app = app_name
	new_page.insert()

	return new_page
