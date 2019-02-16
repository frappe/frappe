function setup_list_filters() {
	const { web_form_doctype, web_form_name } = web_form_settings;

	frappe.call('frappe.website.doctype.web_form.web_form.get_form_data', {
		doctype: web_form_doctype, web_form_name
	})
	.then((r) => {
		if (!r.message) return;
		const web_form = r.message.web_form;

		web_form_filters = web_form.web_form_fields.filter(df => {
			return df.show_in_filter
				&& !['Text', 'Text Editor', 'Attach', 'Attach Image', 'Read Only'].includes(df.fieldtype)
				&& !df.readonly
		}).map(df => {
			const value = frappe.utils.get_query_params()[df.fieldname];
			const f = frappe.ui.form.make_control({
				df: {
					fieldname: df.fieldname,
					fieldtype: df.fieldtype,
					label: df.label,
					options: df.options,
					is_filter: true,
					change: (e) => {
						const query_params = Object.assign(frappe.utils.get_query_params(), {
							[df.fieldname]: f.get_value()
						})
						const query_string = frappe.utils.make_query_string(query_params);
						window.location.replace(query_string)
					}
				},
				parent: $('.list-filters'),
				render_input: true
			});

			$(f.wrapper).addClass('col-md-3');

			if (value) {
				f.set_input(value);
			}

			return f;
		});
	});
}

frappe.ready(setup_list_filters);
