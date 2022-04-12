from __future__ import unicode_literals

import frappe


def execute():
	frappe.reload_doc("core", "doctype", "domain")
	frappe.reload_doc("core", "doctype", "has_domain")
	active_domains = frappe.get_active_domains()
	all_domains = frappe.get_all("Domain")

	for d in all_domains:
		if d.name not in active_domains:
			inactive_domain = frappe.get_doc("Domain", d.name)
			inactive_domain.setup_data()
			inactive_domain.remove_custom_field()
