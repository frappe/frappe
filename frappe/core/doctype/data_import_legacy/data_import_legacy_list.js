frappe.listview_settings['Data Import Legacy'] = {
	add_fields: ["import_status"],
	has_indicator_for_draft: 1,
	get_indicator: function(doc) {

		let status = {
			'Successful': [__("Success"), "green", "import_status,=,Successful"],
			'Partially Successful': [__("Partial Success"), "blue", "import_status,=,Partially Successful"],
			'In Progress': [__("In Progress"), "orange", "import_status,=,In Progress"],
			'Failed': [__("Failed"), "red", "import_status,=,Failed"],
			'Pending': [__("Pending"), "orange", "import_status,=,"]
		}

		if (doc.import_status) {
			return status[doc.import_status];
		}

		if (doc.docstatus == 0) {
			return status['Pending'];
		}

		return status['Pending'];
	}
};
