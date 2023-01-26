# Copyright (c) 2019, Frappe Technologies and contributors
# License: MIT. See LICENSE

import frappe
from frappe.model.document import Document


class CommunicationLink(Document):
	pass


def on_doctype_update():
	frappe.db.add_index("Communication Link", ["link_doctype", "link_name"])
