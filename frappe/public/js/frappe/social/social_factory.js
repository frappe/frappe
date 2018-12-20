frappe.views.SocialFactory = class SocialFactory extends frappe.views.Factory {
	show() {
		if (frappe.pages.social) {
			frappe.container.change_to('social');
		} else {
			this.make('social');
		}
	}

	make(page_name) {
		const assets = [
			'/assets/js/social.min.js'
		];

		frappe.require(assets, () => {
			frappe.social.home = new frappe.social.Home({
				parent: this.make_page(true, page_name)
			});
		});
	}
};
