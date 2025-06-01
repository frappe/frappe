nts.pages["user-profile"].on_page_load = function (wrapper) {
	nts.require("user_profile_controller.bundle.js", () => {
		let user_profile = new nts.ui.UserProfile(wrapper);
		user_profile.show();
	});
};
