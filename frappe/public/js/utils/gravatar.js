const get_gravatar = function(email) {
	return frappe.call('frappe.desk.page.setup_wizard.setup_wizard.get_gravatar', { email })
		.then(r => r.message);
};

frappe.get_gravatar = get_gravatar;
export default get_gravatar;
