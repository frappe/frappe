frappe.pages['user-profile'].on_page_load = function (wrapper) {
	frappe.require('assets/js/user_profile_controller.min.js', () => {
		let user_profile = new frappe.ui.UserProfile(wrapper);
		user_profile.show();
	});
};