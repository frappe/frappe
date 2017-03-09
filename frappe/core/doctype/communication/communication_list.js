frappe.listview_settings['Communication'] = {
	add_fields: [
		"sent_or_received","recipients", "subject",
		"communication_medium", "communication_type",
		"sender", "seen"
	],

	filters: [["status", "=", "Open"]],

	onload: function(listview) {
		method = "frappe.email.inbox.create_email_flag_queue"

		listview.page.add_menu_item(__("Mark as Read"), function() {
			listview.call_for_selected_items(method, { action: "Read" })
		});
		listview.page.add_menu_item(__("Mark as Unread"), function() {
			listview.call_for_selected_items(method, { action: "Unread" })
		});
	}
};
