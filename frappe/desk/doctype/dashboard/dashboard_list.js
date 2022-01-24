frappe.listview_settings['Dashboard'] = {
	button: {
		show(doc) {
			return doc.name;
		},
		get_label() {
			return '\u2197';
		},
		get_description(doc) {
			return __('View {0}', [`${doc.name}`]);
		},
		action(doc) {
			frappe.set_route('dashboard-view', doc.name);
		}
	},
}