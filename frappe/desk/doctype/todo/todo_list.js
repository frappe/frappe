frappe.listview_settings['ToDo'] = {
	onload: function(me) {
		if (!frappe.route_options) {
			frappe.route_options = {
				"owner": frappe.session.user,
				"status": "Open"
			};
		}
		me.page.set_title(__("To Do"));
	},
	hide_name_column: true,
	refresh: function(me) {
		// override assigned to me by owner
		if (me.todo_sidebar_setup) return;

		me.page.sidebar.find(".assigned-to-me a").off("click").on("click", function() {
			me.filter_area.remove("assigned_by");
			me.filter_area.add([[me.doctype, "owner", '=', frappe.session.user]]);
		});

		// add assigned by me
		me.page.add_sidebar_item(__("Assigned By Me"), function() {
			me.filter_area.remove("owner");
			me.filter_area.add([[me.doctype, "assigned_by", '=', frappe.session.user]]);
		}, ".assigned-to-me");

		me.todo_sidebar_setup = true;
	},
	add_fields: ["reference_type", "reference_name"],
}
