export default class Document {
	constructor(data, name) {
		Object.assign(this, data);
	}

	get_meta() {
		if (this.doctype) {

		}
	}

	get(key) {
		return this[key];
	}

	set(key, value) {
		this[key] = value;
	}

	append(key, document) {
		if (!this[key]) {
			this[key] = [];
		}
		this[key].push(this.init_doc(document));
	}

	init_doc(data) {
		if (data.prototype instanceof Document) {
			return data;
		} else {
			return new Document(d);
		}
	}

	validate() {

	}
};