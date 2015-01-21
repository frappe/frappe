frappe.listview_settings["Email Account"] = {
	add_fields: ["default_incoming", "default_outgoing"],
	get_indicator: function(doc) {
		if(doc.default_incoming && doc.default_outgoing) {
			return [__("Default Sending and Inbox"), "blue", "default_incoming,=,Yes|default_outgoing,=,Yes"]
		}
		else if(doc.default_incoming) {
			return [__("Default Inbox"), "blue", "default_incoming,=,Yes"];
		}
		else if(doc.default_outgoing) {
			return [__("Default Sending"), "blue", "default_outgoing,=,Yes"];
		}
		else {
			return [__("Inbox"), "darkgrey", "is_global,=,No|is_default=No"];
		}
	}
}
