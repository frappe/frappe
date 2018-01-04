frappe.listview_settings['Chat Room'] = {
	filters: [
		['Chat Room', 'owner', '==', frappe.session.user, true],
		['Chat Room', 'users', 'in', frappe.session.user, true]
	]
};