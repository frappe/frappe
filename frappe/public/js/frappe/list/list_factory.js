// Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
// MIT License. See license.txt

frappe.provide('frappe.views.list_view');

window.cur_list = null;
frappe.views.ListFactory = class ListFactory extends frappe.views.Factory {
	make (route) {
		const me = this;
		const doctype = route[1];

		// List / Gantt / Kanban / etc
		// File is a special view
		const view_name = doctype !== 'File' ? frappe.utils.to_title_case(route[2] || 'List') : 'File';
		let view_class = frappe.views[view_name + 'View'];
		if (!view_class) view_class = frappe.views.ListView;

		frappe.provide('frappe.views.list_view.' + doctype);
		frappe.views.list_view[me.page_name] = new view_class({
			doctype: doctype,
			parent: me.make_page(true)
		});
	}

	teardown() {
		if (window.cur_list !== null) {
			window.cur_list.teardown();
		}
		window.cur_list = null;
	}

	before_show() {
		this.set_module_breadcrumb();
	}

	on_show() {
		window.cur_list = frappe.views.list_view[this.page_name];
		window.cur_list.show();
	}

	set_module_breadcrumb() {
		if (frappe.route_history.length > 1) {
			const prev_route = frappe.route_history[frappe.route_history.length - 2];
			if (prev_route[0] === 'modules') {
				const doctype = this.route[1], module = prev_route[1];
				if (frappe.module_links[module] && frappe.module_links[module].includes(doctype)) {
					// save the last page from the breadcrumb was accessed
					frappe.breadcrumbs.set_doctype_module(doctype, module);
				}
			}
		}
	}
}
