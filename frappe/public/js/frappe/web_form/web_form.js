frappe.ready(function() {
	const { web_form_doctype, doc_name, web_form_name } = web_form_settings;
	const wrapper = $(".web-form-wrapper");
	get_data().then(res => {
		const data = setup_fields(res.message);
		data.doc = res.message.doc
		data.web_form.doc_name = web_form_settings.doc_name

		let web_form = new frappe.ui.WebForm({
			parent: wrapper,
			fields: data.web_form.web_form_fields,
			doc: data.doc,
			...data.web_form,
		});

		web_form.make();
		document.querySelector("body").style.display = "block";
	});

	function get_data() {
		return frappe.call({
			method: "frappe.website.doctype.web_form.web_form.get_form_data",
			args: {
				doctype: web_form_doctype,
				docname: doc_name,
				web_form_name: web_form_name
			},
			freeze: true
		});
	}

	function setup_fields(form_data) {
		const query_params = frappe.utils.get_query_params();

		form_data.web_form.web_form_fields.map(df => {
			if (df.fieldtype === "Table") {
				df.get_data = () => {
					let data = [];
					if (form_data.doc) {
						data = form_data.doc[df.fieldname];
					}
					return data;
				};

				df.options = null;

				if (form_data.hasOwnProperty(df.fieldname)) {
					df.fields = form_data[df.fieldname];
				}

				if (df.fieldtype === "Attach") {
					df.is_private = true;
				}

				// Set defaults
				if (
					query_params &&
					query_params["new"] == 1 &&
					df.fieldname in query_params
				) {
					df.default = query_params[df.fieldname];
				}

				df.is_web_form = true;

				delete df.parent;
				delete df.parentfield;
				delete df.parenttype;
				delete df.doctype;

				return df;
			}
		});

		return form_data;
	}
});