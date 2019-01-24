frappe.views.ModulesFactory = class ModulesFactory extends frappe.views.Factory {
	show() {
		if (frappe.pages.modules) {
			frappe.container.change_to('modules');
		} else {
			this.make('modules');
		}
	}

	make(page_name) {
		const assets = [
			'/assets/js/modules.min.js'
		];

		frappe.require(assets, () => {
			frappe.modules.home = new frappe.modules.Home({
				parent: this.make_page(true, page_name)
			});
		});
	}
};
