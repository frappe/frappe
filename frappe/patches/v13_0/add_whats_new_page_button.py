
import frappe

def execute():
	frappe.reload_doc('core', 'doctype', 'navbar_settings')
	frappe.reload_doc('core', 'doctype', 'navbar_item')

	navbar_settings = frappe.get_single("Navbar Settings")
	found = 0

	for item in navbar_settings.get('help_dropdown'):
		if item.item_label == "Whats New" and item.route == "/app/whats-new-page":
			found = 1

	if not found:
		whats_new_button = {
				'item_label': 'Whats New',
				'item_type': "Route",
				'route': "/app/whats-new-page",
				'is_standard': 1
			}
		navbar_settings.append('help_dropdown', whats_new_button)
		navbar_settings.save()