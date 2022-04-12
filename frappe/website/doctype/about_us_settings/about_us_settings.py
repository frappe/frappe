# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

# For license information, please see license.txt

from __future__ import unicode_literals

import frappe
from frappe.model.document import Document


class AboutUsSettings(Document):
	def on_update(self):
		from frappe.website.render import clear_cache

		clear_cache("about")


def get_args():
	obj = frappe.get_doc("About Us Settings")
	return {"obj": obj}
