import frappe

@frappe.whitelist()
def get_settings_to_show(doctype, docname):
	doc = frappe.get_doc(doctype, docname)
	# settings_config = frappe.parse_json(settings_config)
	print_settings = frappe.get_single('Print Settings')

	if hasattr(doc, 'get_print_settings'):
		fields = doc.get_print_settings() or []
	else:
		return []

	print_settings_fields = []
	for fieldname in fields:
		df = print_settings.meta.get_field(fieldname)
		df.default = print_settings.get(fieldname)
		print_settings_fields.append(df)

	# for key in settings_config:
	# 	config = frappe._dict(settings_config[key])
	# 	if frappe.get_attr(config.condition)(doc):
	# 		df = print_settings.meta.get_field(key)
	# 		settings[key] = {
	# 			'fieldtype': df.fieldtype,
	# 			'label': df.label,
	# 			'default': print_settings.get(key),
	# 			# 'child_field': config.child_field,
	# 			# 'set_template': config.set_template
	# 		}
	return print_settings_fields
