export default class WebForm {
	constructor(options) {
		// wrapper, doctype, docname, web_form_name, allow_incomplete
		Object.assign(this, options);

		this.get_data();
	}

	get_data() {
		frappe.call({
			method: 'frappe.website.doctype.web_form.web_form.get_form_data',
			args: {
				doctype: this.doctype,
				docname: this.docname,
				web_form_name: this.web_form_name
			},
			freeze: true
		}).then(r => {
			const { doc, web_form } = r.message;
			console.log(doc, web_form);
			this.render(doc, web_form);
		});
	}

	render(doc, web_form) {
		web_form.web_form_fields.map(df => {
			if (df.fieldtype === 'Link') {
				df.fieldtype = 'Select';
			}

			if (df.fieldtype === 'Table') {
				df.get_data = () => {
					let data = []
					if(doc) {
						data = doc[df.fieldname];
					}
					return data;
				}

				df.fields = [
					{
						fieldtype: 'Link',
						fieldname: "role",
						options: "Role",
						label: __("Role"),
						in_list_view: 1
					}
				];

				df.options = null;
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
		if(doc) {
			this.fieldGroup.set_values(doc);
		}
	}

	get_values() {
		let values = this.fieldGroup.get_values(this.allow_incomplete);
		values.doctype = this.doctype;
		values.name = this.docname;
		values.web_form_name = this.web_form_name;
		return values;
	}
}