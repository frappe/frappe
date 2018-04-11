frappe.provide('frappe.success_action');

frappe.success_action['ToDo'] = {
	first_creation_message: __('Congratulations on creating your first ToDo! 🎉'),
	message: __('ToDo created successfully'),
	actions: [
		'New',
		'Print',
		'Email'
	],
};
