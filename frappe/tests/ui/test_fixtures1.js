$.extend(frappe.test_data, {
	'User': {
		'User 1': [
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
	},
	'ToDo': {
		'ToDo 1': [
			{description: 'ToDo 1'},
			{status: 'Open'},
			{priority: 'Low'},
			{date: '2017-07-05'}
		],
		'ToDo 2': [
			{description: 'ToDo 2'},
			{status: 'Open'},
			{priority: 'Medium'},
			{date: '2017-07-05'},
			{owner: 'user1@mail.com'}
		],
		'ToDo 3': [
			{description: 'ToDo 3'},
			{status: 'Open'},
			{priority: 'High'},
			{date: '2018-09-20'}
		],
		'ToDo 4': [
			{description: 'ToDo 4'},
			{status: 'Closed'},
			{priority: 'Low'},
			{date: '2017-07-05'}
		],
		'ToDo 5': [
			{description: 'ToDo 5'},
			{status: 'Closed'},
			{priority: 'Low'},
			{date: '2017-07-05'}
		],
		'ToDo 6': [
			{description: 'ToDo 6'},
			{status: 'Closed'},
			{priority: 'High'},
			{date: '2017-07-05'},
			{owner: 'user1@mail.com'}
		]
	}
});