# Copyright (c) 2018, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

import frappe


def execute():
	signatures = frappe.db.get_list(
		"User", {"email_signature": ["!=", ""]}, ["name", "email_signature"]
	)
	frappe.reload_doc("core", "doctype", "user")
	for d in signatures:
		signature = d.get("email_signature")
		signature = signature.replace("\n", "<br>")
		signature = "<div>" + signature + "</div>"
		frappe.db.set_value("User", d.get("name"), "email_signature", signature)
