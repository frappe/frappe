frappe.listview_settings['Chat Room'] = {
	filters: [
		['Chat Room', 'owner', '=', frappe.session.user, true],
		['Chat Room User', 'user', '=', frappe.session.user, true]
	]
};