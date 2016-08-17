frappe.listview_settings['Communication'] = {
	add_fields: ["sent_or_received", "recipients", "subject", "communication_medium", "communication_type"],
	//default_filters: [["Communication", "communication_type", "=", "Communication"]],
	filters: [["status", "=", "Open"]]
};
