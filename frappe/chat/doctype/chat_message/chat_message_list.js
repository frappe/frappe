frappe.listview_settings['Chat Message'] = {
	filters: [
		['Chat Message', 'user',  '==', frappe.session.user, true]
		// I need an or_filter here.
		// ['Chat Room',    'owner', '==', frappe.session.user, true],
		// ['Chat Room',    frappe.session.user, 'in', 'users', true]
	]
};