frappe.ready(function() {
	const { web_form_doctype, doc_name, web_form_name } = web_form_settings;
	const wrapper = $(".web-form-wrapper");
	if (web_form_settings.login_required && frappe.session.user === "Guest") {
		const login_required = new frappe.ui.Dialog({
			title: __("Not Permitted"),
			primary_action_label: __("Login"),
			primary_action: () => {
				window.location.replace('/login?redirect-to=/' + web_form_name)
			}
		});
		login_required.set_message(__("You are not permitted to access this page."));
		login_required.show();
	}

	else if (web_form_settings.is_list) {
		web_form_list = new frappe.views.WebFormList({
			parent: wrapper,
			doctype: web_form_doctype,
			web_form_name: web_form_name,
			settings: web_form_settings
		})
	}

	else {
		// If editing is not allowed redirect to a new form
		if (web_form_settings.doc_name && web_form_settings.allow_edit === 0) {
			window.location.replace(window.location.pathname + "?new=1")
		}
		get_data().then(res => {
			const data = setup_fields(res.message);
			data.web_form.is_new = web_form_settings.is_new;
			data.doc = res.message.doc
			data.web_form.doc_name = web_form_settings.doc_name

			let web_form = new frappe.ui.WebForm({
				parent: wrapper,
				fields: data.web_form.web_form_fields,
				doc: data.doc,
				...data.web_form,
			});
			web_form.make()
		})
	}

	setTimeout(() => {
		document.querySelector("body").style.display = "block";
		frappe.init_client_script && frappe.init_client_script();
		frappe.web_form.after_load && frappe.web_form.after_load();
	}, 500);

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

				df.fields = form_data[df.fieldname];

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
			if (df.fieldtype === "Link") df.only_select = true;
		});

		return form_data;
	}
});