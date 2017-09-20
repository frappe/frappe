frappe.listview_settings['Communication'] = {
	add_fields: [
		"sent_or_received","recipients", "subject",
		"communication_medium", "communication_type",
		"sender", "seen", "reference_doctype", "reference_name",
		"has_attachment"
	],

	filters: [["status", "=", "Open"]],

	onload: function(list_view) {
		let method = "frappe.email.inbox.create_email_flag_queue"

		list_view.page.add_menu_item(__("Mark as Read"), function() {
			list_view.call_for_selected_items(method, { action: "Read" });
		});
		list_view.page.add_menu_item(__("Mark as Unread"), function() {
			list_view.call_for_selected_items(method, { action: "Unread" });
		});
	},

	set_primary_action: function(list_view) {
		var me = this;
		if (list_view.new_doctype) {
			list_view.page.set_primary_action(
				__("New"),
				function() { new frappe.views.CommunicationComposer({ doc: {} }) },
				"octicon octicon-plus"
			);
		} else {
			list_view.page.clear_primary_action();
		}
	}
};
