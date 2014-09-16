import frappe

def execute():
	changed = (
		("custom", ("custom_field", "custom_script", "customize_form",
			 "customize_form_field", "property_setter")),
		("desk", ("event", "event_role", "event_user", "todo", "feed",
			"note", "note_user")),
		("email", ("bulk_email", "email_alert", "email_alert_recipient",
			"standard_reply")),
		("geo", ("country", "currency")),
		("print", ("letter_head", "print_format", "print_settings"))
	)
	for module in changed:
		for doctype in module[1]:
			frappe.reload_doc(module[0], "doctype", doctype)
