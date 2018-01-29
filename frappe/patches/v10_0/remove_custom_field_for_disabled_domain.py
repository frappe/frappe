import frappe

def execute():
	active_domains = frappe.get_active_domains()
	all_domains = (frappe.get_hooks('domains') or {}).keys()

	for domain in all_domains:
		if domain not in active_domains:
			inactive_domain = frappe.get_doc("Domain", domain)
			inactive_domain.setup_data()
			inactive_domain.remove_custom_field()
