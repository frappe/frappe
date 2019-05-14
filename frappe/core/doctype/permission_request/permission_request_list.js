frappe.listview_settings['Permission Request'] = {
	get_indicator: function (doc) {
		if (doc.status === "Requested") {
			return [__("Requested"), "orange", "status,=,Requested"];
		} else if (doc.status === "Approved") {
			return [__("Approved"), "green", "status,=,Approved"];
		} else if (doc.status === "Denied") {
			return [__("Denied"), "red", "status,=,Denied"];
		}
	}
};
