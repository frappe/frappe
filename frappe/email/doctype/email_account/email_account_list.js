frappe.listview_settings["Email Account"] = {
	add_fields: ["is_global", "is_default"],
	get_indicator: function(doc) {
		if(doc.is_default && doc.is_global) {
			return [__("Global Default"), "green", "is_default,=,Yes|is_global,=,Yes"]
		}
		else if(doc.is_default) {
			return [__("Default"), "blue", "is_default,=,Yes"];
		}
		else if(doc.is_global) {
			return [__("Global"), "green", "is_global,=,Yes"];
		}
		else  {
			return [__("Personal"), "darkgrey", "is_global,=,No|is_default=No"];
		}
	}
}
