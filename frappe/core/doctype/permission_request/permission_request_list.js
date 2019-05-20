frappe.listview_settings['Permission Request'] = {
	get_indicator: function (doc) {
		let status_map = {
			"Requested": "orange",
			"Approved": "green",
			"Denied": "red"
		}

		return [__(doc.status), status_map[doc.status], "status,=," + doc.status];
	}
};
