frappe.wiz.on("after_load", function() {
	if (frappe.boot.frappe_limits.user_limit===1) {
		// remove users slide
		var users_slide;
		for (var i in frappe.wiz.wizard.slides) {
			var slide = frappe.wiz.wizard.slides[i];
			if (slide.title === frappe.wiz.user.title) {
				users_slide = i;
				break;
			}
		}

		if (users_slide >= 0) {
			frappe.wiz.wizard.slides.splice(users_slide, 1);
		}

	}
});
