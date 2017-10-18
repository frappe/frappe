import FileStorage from './file_storage';
import get_meta from './meta';

export class Frappe {
	constructor() {
		this.init();
	}

	init() {
		this.storage = new FileStorage();
	}

	get_meta(doctype) {
		return get_meta(doctype);
	}
}

let frappe = new Frappe();

export default frappe;