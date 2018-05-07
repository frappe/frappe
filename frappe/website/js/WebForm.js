export default class WebForm {
	constructor(wrapper, doctype, docname, web_form_name) {
		this.wrapper = wrapper;
		this.doctype = doctype;
		this.docname = docname;
		this.web_form_name = web_form_name;

		this.get_data();
	}

	get_data() {
		frappe.call({
			method: 'frappe.website.doctype.web_form.web_form.get_form_data',
			args: {
				doctype: this.doctype,
				docname: this.docname,
				web_form_name: this.web_form_name
			}
		}).then(r => {
			const { doc, web_form } = r.message;
			this.render(doc, web_form);
		});
	}

	render(doc, web_form) {
		const fields = web_form.web_form_fields.map(df => {
			if (df.fieldtype === 'Link') {
				df.fieldtype = 'Select';
			}

			delete df.parent;
			delete df.parentfield;
			delete df.parenttype;
			delete df.doctype;

			return df;
		});

		this.fieldGroup = new frappe.ui.FieldGroup({
			parent: this.wrapper,
			fields: web_form.web_form_fields
		});

		this.fieldGroup.make();
		this.fieldGroup.set_values(doc);
	}

	get_values() {
		return this.fieldGroup.get_values();
	}
}