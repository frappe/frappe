let imports_in_progress = [];

frappe.listview_settings['Data Import'] = {
	add_fields: ["import_log"],
	onload(listview) {
		frappe.realtime.on('data_import_progress', data => {
			if (!imports_in_progress.includes(data.data_import)) {
				imports_in_progress.push(data.data_import);
			}
		});
		frappe.realtime.on('data_import_refresh', data => {
			imports_in_progress = imports_in_progress.filter(
				d => d !== data.data_import
			);
			listview.refresh();
		});
	},
	get_indicator: function(doc) {
		var colors = {
			'Pending': 'orange',
			'Not Started': 'orange',
			'Partial Success': 'orange',
			'Partially Completed': 'orange',
			'Success': 'green',
			'In Progress': 'orange',
			'Error': 'red'
		};
		let status = doc.status;
		let import_log = JSON.parse(doc.import_log || '[]');

		if (imports_in_progress.includes(doc.name)) {
			status = 'In Progress';
		}
		if (status == 'Pending') {
			status = 'Not Started';
		}
		if (doc.status == 'Pending' && import_log.length > 0) {
			status = 'Partially Completed';
		}

		return [__(status), colors[status], 'status,=,' + doc.status];
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
