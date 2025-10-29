// Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
// MIT License. See license.txt

frappe.provide("frappe.pages");
frappe.provide("frappe.views");

frappe.views.Factory = class Factory {
	constructor(opts) {
		$.extend(this, opts);
	}

	show() {
		this.route = frappe.get_route();
		this.page_name = frappe.get_route_str();

		if (this.before_show && this.before_show() === false) return;

		if (frappe.pages[this.page_name]) {
			frappe.container.change_to(this.page_name);
			if (this.on_show) {
				this.on_show();
			}
		} else {
			if (this.route[1]) {
				this.make(this.route);
			} else {
				frappe.show_not_found(this.route);
			}
		}
	}

	make_page(double_column, page_name, sidebar_postition) {
		return frappe.make_page(double_column, page_name, sidebar_postition);
	}
};

frappe.make_page = function (double_column, page_name, sidebar_position) {
	if (!page_name) {
		page_name = frappe.get_route_str();
	}

	const page = frappe.container.add_page(page_name);

	frappe.ui.make_app_page({
		parent: page,
		single_column: !double_column,
		sidebar_position: sidebar_position,
		disable_sidebar_toggle: !sidebar_position,
	});

	frappe.container.change_to(page_name);
	return page;
};
