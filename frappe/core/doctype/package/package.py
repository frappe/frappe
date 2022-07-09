# Copyright (c) 2021, Frappe Technologies and contributors
# For license information, please see license.txt

import os

import frappe
from frappe.model.document import Document


class Package(Document):
	def validate(self):
		if not self.package_name:
			self.package_name = self.name.lower().replace(" ", "-")


@frappe.whitelist()
def get_license_text(license_type):
	with open(os.path.join(os.path.dirname(__file__), "licenses", license_type + ".md")) as textfile:
		return textfile.read()
