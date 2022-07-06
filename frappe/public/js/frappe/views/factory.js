// Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
// MIT License. See license.txt

frappe.provide('frappe.pages');
frappe.provide('frappe.views');

frappe.views.Factory = class Factory {
	constructor(opts) {
		$.extend(this, opts);
	}

	show() {
		this.route = frappe.get_route();
		this.page_name = frappe.get_route_str();

		if (this.before_show && this.before_show() === false) return;

		if (this.route[1]) {
			this.make(this.route);
			if (this.on_show) {
				this.on_show();
			}
		} else {
			frappe.show_not_found(this.route);
		}
	}

	teardown() {
		if (this.on_teardown) {
			this.on_teardown();
		}

		if (this.created_page_name !== undefined) {
			frappe.container.remove_page(this.created_page_name);
		}
	}

	make_page(double_column) {
		this.created_page_name = this.page_name
		const page = frappe.container.add_page(this.page_name);

		frappe.ui.make_app_page({
			parent: page,
			single_column: !double_column
		});

		frappe.container.change_to(this.page_name);
		return page;
	}
}
