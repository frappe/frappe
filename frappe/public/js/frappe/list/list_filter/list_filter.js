import { ListFilterAPI } from "./list_filter_api";
import { ListFilterMenu } from "./list_filter_menu";

frappe.provide("frappe.ui");

/** Saved layout dropdown for list view (menu display only; actions wired later). */
export default class ListFilter {
	/** Label for the built-in default layout row. */
	get default_layout_label() {
		return __("Default Layout");
	}

	constructor(list_view) {
		this.list_view = list_view;
		Object.assign(this, arguments[0]);
		this.filters = [];
		this.active_layout_name = "default_layout";
		this.active_layout_label = this.default_layout_label;
		this.setup_promise = this.setup_layout_menu({ initial_setup: true });
	}
}

Object.assign(ListFilter.prototype, ListFilterMenu, ListFilterAPI);
