frappe.listview_settings["ToDo"] = {
	hide_name_column: true,
	add_fields: ["reference_type", "reference_name"],

	onload: function (me) {
		if (!Object.keys(frappe.route_options).length) {
			frappe.route_options = {
				allocated_to: frappe.session.user,
				status: "Open",
			};
		}
		me.page.set_title(__("To Do"));
	},

	button: {
		show: function (doc) {
			return doc.reference_name;
		},
		get_label: function () {
			return __("Open", null, "Access");
		},
		get_description: function (doc) {
			return __("Open {0}", [`${__(doc.reference_type)}: ${doc.reference_name}`]);
		},
		action: function (doc) {
			frappe.set_route("Form", doc.reference_type, doc.reference_name);
		},
	},
};
