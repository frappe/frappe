frappe.listview_settings['Energy Point Log'] = {
	hide_name_column: true,
	add_fields: ['type', 'reference_doctype', 'reference_name'],
	get_indicator: function (doc) {
		let colors = {
			'Appreciation': 'green',
			'Criticism': 'red',
			'Auto': 'blue',
			'Revert': 'orange',
			'Review': 'grey'
		};
		return [__(doc.type), colors[doc.type], "type,=," + doc.type];
	},

	button: {
		show: function(doc) {
			return doc.reference_name;
		},
		get_label: function() {
			return __('View Ref');
		},
		get_description: function(doc) {
			return __('Open {0}', [`${doc.reference_doctype} ${doc.reference_name}`]);
		},
		action: function(doc) {
			frappe.set_route('Form', doc.reference_doctype, doc.reference_name);
		}
	}
};
