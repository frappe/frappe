// Copyright (c) 2015, nts Technologies Pvt. Ltd. and Contributors
// MIT License. See license.txt

nts.provide("nts.pages");
nts.provide("nts.views");

nts.views.Factory = class Factory {
	constructor(opts) {
		$.extend(this, opts);
	}

	show() {
		this.route = nts.get_route();
		this.page_name = nts.get_route_str();

		if (this.before_show && this.before_show() === false) return;

		if (nts.pages[this.page_name]) {
			nts.container.change_to(this.page_name);
			if (this.on_show) {
				this.on_show();
			}
		} else {
			if (this.route[1]) {
				this.make(this.route);
			} else {
				nts.show_not_found(this.route);
			}
		}
	}

	make_page(double_column, page_name, hide_sidebar) {
		return nts.make_page(double_column, page_name, hide_sidebar);
	}
};

nts.make_page = function (double_column, page_name, disable_sidebar_toggle) {
	if (!page_name) {
		page_name = nts.get_route_str();
	}

	const page = nts.container.add_page(page_name);

	nts.ui.make_app_page({
		parent: page,
		single_column: !double_column,
		disable_sidebar_toggle: disable_sidebar_toggle,
	});

	nts.container.change_to(page_name);
	return page;
};
