frappe.listview_settings["Email Account"] = {
	add_fields: ["default_incoming", "default_outgoing", "enable_incoming", "enable_outgoing"],
	primary_action: () =>
		frappe.user.has_role("System Manager")
			? open_email_settings({ add: true })
			: frappe.new_doc("Email Account"),
	onload(listview) {
		if (frappe.user.has_role("System Manager")) {
			listview.page.add_inner_button(__("Email Settings"), () => open_email_settings());
		}
	},
	get_indicator: function (doc) {
		if (doc.default_incoming && doc.default_outgoing) {
			var color = doc.enable_incoming && doc.enable_outgoing ? "blue" : "gray";
			return [
				__("Default Sending and Inbox"),
				color,
				"default_incoming,=,Yes|default_outgoing,=,Yes",
			];
		} else if (doc.default_incoming) {
			color = doc.enable_incoming ? "blue" : "gray";
			return [__("Default Inbox"), color, "default_incoming,=,Yes"];
		} else if (doc.default_outgoing) {
			color = doc.enable_outgoing ? "blue" : "gray";
			return [__("Default Sending"), color, "default_outgoing,=,Yes"];
		} else if (doc.enable_incoming && doc.enable_outgoing) {
			return [
				__("Sending and Inbox"),
				"blue",
				"enable_incoming,=,Yes|enable_outgoing,=,Yes",
			];
		} else if (doc.enable_outgoing) {
			return [__("Sending"), "blue", "enable_outgoing,=,Yes|enable_incoming,=,No"];
		} else if (doc.enable_incoming) {
			return [__("Inbox"), "blue", "enable_incoming,=,Yes|enable_outgoing,=,No"];
		} else {
			return [__("Disabled"), "gray", "enable_incoming,=,No|enable_outgoing,=,No"];
		}
	},
};

frappe.help.youtube_id["Email Account"] = "YFYe0DrB95o";

function open_email_settings(opts) {
	frappe.require("email_settings.bundle.js", () => frappe.email_settings.open(opts));
}
