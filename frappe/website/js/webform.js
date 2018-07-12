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
			const { doc, web_form, links } = r.message;
			this.render(doc, web_form, links);
		});
	}

	render(doc, web_form, links) {
		web_form.web_form_fields.map(df => {
			if (df.fieldtype === 'Link') {
				df.fieldtype = 'Select';
				df.options = links[df.fieldname]
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
						in_list_view: 1 // added
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

		this.field_group = new frappe.ui.FieldGroup({
			parent: this.wrapper,
			fields: web_form.web_form_fields
		});

		this.field_group.make();

		this.wrapper.find(".form-column").unwrap(".section-body");

		if(doc) {
			this.field_group.set_values(doc);
		}
	}

	get_values() {
		let values = this.field_group.get_values(this.allow_incomplete);
		if (!values) return null;
		values.doctype = this.doctype;
		values.name = this.docname;
		values.web_form_name = this.web_form_name;
		return values;
	}
}
