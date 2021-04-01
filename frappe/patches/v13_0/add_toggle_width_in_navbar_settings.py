from __future__ import unicode_literals
import frappe

def execute():
	navbar_settings = frappe.get_single("Navbar Settings")

	if frappe.db.exists('Navbar Item', {'item_label': 'Toggle Full Width'}):
		return

	for navbar_item in navbar_settings.settings_dropdown[5:]:
		navbar_item.idx = navbar_item.idx + 1

	navbar_settings.append('settings_dropdown', {
		'item_label': 'Toggle Full Width',
		'item_type': 'Action',
		'action': 'frappe.ui.toolbar.toggle_full_width()',
		'is_standard': 1,
		'idx': 6
	})

	navbar_settings.save()