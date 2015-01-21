frappe.listview_settings["Email Account"] = {
	add_fields: ["default_incoming", "default_outgoing", "enable_incoming", "enable_outgoing"],
	get_indicator: function(doc) {
		if(doc.default_incoming && doc.default_outgoing) {
			var color = (doc.enable_incoming && doc.enable_outgoing) ? "blue" : "darkgrey";
			return [__("Default Sending and Inbox"), color, "default_incoming,=,Yes|default_outgoing,=,Yes"]
		}
		else if(doc.default_incoming) {
			var color = doc.enable_incoming ? "blue" : "darkgrey";
			return [__("Default Inbox"), color, "default_incoming,=,Yes"];
		}
		else if(doc.default_outgoing) {
			var color = doc.enable_outgoing ? "blue" : "darkgrey";
			return [__("Default Sending"), color, "default_outgoing,=,Yes"];
		}
		else {
			var color = doc.enable_incoming ? "blue" : "darkgrey";
			return [__("Inbox"), color, "is_global,=,No|is_default=No"];
		}
	}
}
