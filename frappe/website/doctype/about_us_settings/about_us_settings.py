# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

# License: MIT. See LICENSE

import frappe
from frappe.model.document import Document


class AboutUsSettings(Document):
	def on_update(self):
		from frappe.website.utils import clear_cache

		clear_cache("about")


def get_args():
	obj = frappe.get_doc("About Us Settings")
	return {"obj": obj}
