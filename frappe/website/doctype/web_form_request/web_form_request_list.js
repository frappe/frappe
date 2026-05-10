frappe.listview_settings["Web Form Request"] = {
	add_fields: ["reference_docname", "expires_on", "used_on"],
	get_indicator: function (doc) {
		const now = frappe.datetime.system_datetime(true);
		const now_string = frappe.datetime.system_datetime();
		const expires_on = frappe.datetime.str_to_obj(doc.expires_on);

		if (doc.used_on) {
			return [__("Used"), "green", "used_on,is,set"];
		} else if (doc.expires_on && expires_on < now) {
			return [__("Expired"), "red", `expires_on,is,set|expires_on,<,${now_string}`];
		} else {
			return [__("Not Used"), "gray", `used_on,is,not set`];
		}
	},
};
