import WebForm from "./web_form";

frappe.ready(function() {
	show_login_prompt();

	if (frappe.web_form_doc) {
		show_form();
	}

	function show_login_prompt() {
		if (frappe.session.user != "Guest") return;
		const login_required = new frappe.ui.Dialog({
			title: __("Not Permitted"),
			primary_action_label: __("Login"),
			primary_action: () => {
				window.location.replace(
					"/login?redirect-to=" + window.location.pathname
				);
			}
		});
		login_required.set_message(
			__("You are not permitted to access this page.")
		);
		login_required.show();
	}

	function show_form() {
		let web_form_doc = frappe.web_form_doc;
		let reference_doc = frappe.reference_doc;
		let web_form = new WebForm({
			parent: $(".web-form-wrapper"),
			is_new: web_form_doc.is_new,
			web_form_name: web_form_doc.name
		});
		setup_fields(web_form_doc);

		let doc = reference_doc || {};

		web_form.prepare(web_form_doc, doc);
		web_form.make();

		if (web_form_doc.is_new) {
			web_form.set_default_values();
		}

		function setup_fields(web_form_doc) {
			web_form_doc.web_form_fields.forEach(df => {
				df.is_web_form = true;
				df.read_only = !web_form_doc.is_new && !web_form_doc.allow_edit;

				if (df.fieldtype === "TableDialog") {
					$.each(df.fields || [], function(_i, field) {
						if (field.fieldtype === "Link") {
							field.only_select = true;
						}
						field.is_web_form = true;
					});

					if (df.fieldtype === "Attach") {
						df.is_private = true;
					}

					delete df.parent;
					delete df.parentfield;
					delete df.parenttype;
					delete df.doctype;

					return df;
				}
				if (df.fieldtype === "Link") {
					df.only_select = true;
				}
				if (["Attach", "Attach Image"].includes(df.fieldtype)) {
					if (typeof df.options !== "object") {
						df.options = {};
					}
					df.options.disable_file_browser = true;
				}
			});
		}
	}
});
