const promises = {};

export async function with_doctype(doctype) {
	if (typeof doctype !== "string") {
		throw new TypeError("Expected doctype to be a string");
	}
	if (!promises[doctype]) {
		promises[doctype] = frappe.model.with_doctype(doctype);
	}
	return promises[doctype];
}

export class Bus {
	constructor() {
		this._listeners = {};
	}

	on(event, callback) {
		if (!this._listeners[event]) {
			this._listeners[event] = [];
		}
		this._listeners[event].push(callback);

		return () => this.off(event, callback);
	}

	off(event, callback) {
		if (!this._listeners[event]) {
			return;
		}
		this._listeners[event] = this._listeners[event].filter((cb) => cb !== callback);
	}

	emit(event, ...args) {
		if (!this._listeners[event]) {
			return;
		}
		this._listeners[event].forEach((cb) => cb(...args));
	}
}

export class CatalogOptions {
	/** @typedef {{ html: HTMLElement } | { component: import('vue').Component} | function | Promise} SmartElement */

	/** @type {string} */
	link_doctype = "";

	/** @type {string[]} */
	search_fields = ["name"];

	/** @type {(search, filters, or_filters, page_index, page_length)} */
	search_function = null;

	/** @type {string} */
	link_fieldname = "";

	/** @type {string | null} */
	quantity_fieldname = null;

	/** @type {string | null} */
	table_fieldname = null;

	/** @type {SmartElement[]} */
	sidebar_contents = [];

	/** @type {SmartElement[]} */
	item_contents = [];

	/** @type {SmartElement[]} */
	item_footer = [];

	/** @type {SmartElement[]} */
	title = [];
}
