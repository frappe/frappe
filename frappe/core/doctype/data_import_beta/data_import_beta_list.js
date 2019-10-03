frappe.listview_settings['Data Import Beta'] = {
	get_indicator: function(doc) {
		var colors = {
			"Pending": "orange",
			"Partial Success": "orange",
			"Success": "green",
		};
		return [__(doc.status), colors[doc.status], "status,=," + doc.status];
	},
	formatters: {
		import_type(value) {
			return {
				'Insert New Records': __('Insert'),
				'Update Existing Records': __('Update')
			}[value];
		}
	},
	hide_name_column: true
};
