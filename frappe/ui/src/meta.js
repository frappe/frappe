import Document from './document';
import frappe from './frappe';

export default function get_meta(doctype) {
	return frappe.storage.get('DocType', doctype)
		.then((data) => {
			return new Meta(data);
		});
}

export class Meta extends Document {
	constructor(data) {
		super(data);
		this.event_handlers = {};
	}

	on(key, fn) {
		if (!this.event_handlers[key]) {
			this.event_handlers[key] = [];
		}
		this.event_handlers[key].push(fn);
	}

	trigger(key) {

	}
}