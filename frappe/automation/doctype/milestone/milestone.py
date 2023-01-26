# Copyright (c) 2019, Frappe Technologies and contributors
# License: MIT. See LICENSE

import frappe
from frappe.model.document import Document


class Milestone(Document):
	pass


def on_doctype_update():
	frappe.db.add_index("Milestone", ["reference_type", "reference_name"])
