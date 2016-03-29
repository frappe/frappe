frappe.listview_settings['ToDo'] = {
	onload: function(me) {
		frappe.route_options = {
			"owner": user,
			"status": "Open"
		};
		me.page.set_title(__("To Do"));

	},
	set_primary_action:function(doclist){
		doclist.page.clear_primary_action();
		doclist.page.set_primary_action(__("New"), function() {
			frappe.prompt({fieldname:'description', fieldtype:'Text', label:'Description', reqd:1},
				function(data) {
					frappe.call({
						method:'frappe.desk.doctype.todo.todo.new_todo',
						args: data
					})
				}, __('New To Do'));
		}, "octicon octicon-plus");
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
