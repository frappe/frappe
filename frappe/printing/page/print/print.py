import frappe

@frappe.whitelist()
def get_settings_to_show(doc, settings_config):
	doc = frappe.parse_json(doc)
	settings_config = frappe.parse_json(settings_config)
	print_settings = frappe.get_single('Print Settings')
	settings = frappe._dict()
	for key in settings_config:
		config = frappe._dict(settings_config[key])
		if frappe.get_attr(config.condition)(doc):
			settings[key] = {
				'fieldtype': config.fieldtype,
				'label': config.label,
				'value': print_settings.get(key),
				'child_field': config.child_field,
				'set_template': config.set_template
			}
	return settings