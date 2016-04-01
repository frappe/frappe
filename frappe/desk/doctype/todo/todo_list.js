frappe.listview_settings['ToDo'] = {
	onload: function(me) {
		frappe.route_options = {
			"owner": user,
			"status": "Open"
		};
		me.page.set_title(__("To Do"));

	},
	refresh: function(me) {
		// override assigned to me by owner
		me.page.sidebar.find(".assigned-to-me a").off("click").on("click", function() {
			var assign_filter = me.filter_list.get_filter("assigned_by");
			assign_filter && assign_filter.remove(true);

			me.filter_list.add_filter(me.doctype, "owner", '=', user);
			me.run();
		});

		// add assigned by me
		me.page.add_sidebar_item(__("Assigned By Me"), function() {
			var assign_filter = me.filter_list.get_filter("owner");
			assign_filter && assign_filter.remove(true);

			me.filter_list.add_filter(me.doctype, "assigned_by", '=', user);
			me.run();
		}, ".assigned-to-me");
	},
	add_fields: ["reference_type", "reference_name"],
}
