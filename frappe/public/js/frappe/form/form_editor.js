frappe.ui.form.FormEditor = class FormEditor {
	constructor({ frm }) {
		this.frm = frm;
	}

	setup() {
		// setup sortable in all column
		for(let section of this.frm.layout.sections) {
			for (let column of section.columns) {
				column.make_sortable();
			}
		}

	}
}
