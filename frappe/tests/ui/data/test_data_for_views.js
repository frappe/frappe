$.extend(frappe.test_data, {
	'User': {
		'user1@mail.com': [
			{first_name: 'User 1'},
			{email: 'user1@mail.com'},
			{send_welcome_email: 0}
		]
	},
	'Kanban Board': {
		'kanban 1': [
			{kanban_board_name: 'kanban 1'},
			{reference_doctype: 'ToDo'},
			{field_name: 'status'}
		]
	}
});