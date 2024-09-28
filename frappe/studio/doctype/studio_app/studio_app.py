# Copyright (c) 2024, Frappe Technologies Pvt Ltd and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document

from studio.utils import camel_case_to_kebab_case


class StudioApp(Document):
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
