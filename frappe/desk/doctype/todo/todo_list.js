frappe.listview_settings['ToDo'] = {
	hide_name_column: true,
	add_fields: ["reference_type", "reference_name"],

	onload: function(me) {
		if (!frappe.route_options) {
			frappe.route_options = {
				"owner": frappe.session.user,
				"status": "Open"
			};
		}
		me.page.set_title(__("To Do"));
	},

	button: {
		show: function(doc) {
			return doc.reference_name;
		},
		get_label: function() {
			return __('Open');
		},
		get_description: function(doc) {
			return __('Open {0}', [`${doc.reference_type} ${doc.reference_name}`])
		},
		action: function(doc) {
			frappe.set_route('Form', doc.reference_type, doc.reference_name);
		}
	},

	refresh: function(me) {
		if (me.todo_sidebar_setup) return;

		// add assigned by me
		me.page.add_sidebar_item(__("Assigned By Me"), function() {
			me.filter_area.add([[me.doctype, "assigned_by", '=', frappe.session.user]]);
		}, ('.list-link[data-view="Kanban"]'));

		me.todo_sidebar_setup = true;
	},
}