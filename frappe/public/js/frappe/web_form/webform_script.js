import WebFormList from "./web_form_list";
import WebForm from "./web_form";

frappe.ready(function () {
	let web_form_doc = frappe.web_form_doc;
	let reference_doc = frappe.reference_doc;

	show_login_prompt();

	web_form_doc.is_list ? show_list() : show_form();

	function show_login_prompt() {
		if (frappe.session.user != "Guest" || !web_form_doc.login_required) return;
		const login_required = new frappe.ui.Dialog({
			title: __("Not Permitted"),
			primary_action_label: __("Login"),
			primary_action: () => {
				window.location.replace("/login?redirect-to=" + window.location.pathname);
			},
		});
		login_required.show();
		login_required.set_message(__("You are not permitted to access this page without login."));
	}

	function show_list() {
		new WebFormList({
			doctype: web_form_doc.doc_type,
			web_form_name: web_form_doc.name,
			list_columns: web_form_doc.list_columns,
			condition_json: web_form_doc.condition_json,
			settings: {
				allow_delete: web_form_doc.allow_delete,
			},
		});
	}

	function show_form() {
		let web_form = new WebForm({
			parent: $(".web-form-wrapper"),
		});
		let doc = reference_doc || {};
		setup_fields(web_form_doc, doc);

		web_form.prepare(web_form_doc, doc);
		web_form.make();

		if (web_form_doc.is_new) {
			web_form.set_default_values();
		}

		$(".file-size").each(function () {
			$(this).text(frappe.form.formatters.FileSize($(this).text()));
		});
	}

	function setup_fields(web_form_doc, doc_data) {
		web_form_doc.web_form_fields.forEach((df) => {
			df.is_web_form = true;
			df.read_only = df.read_only || (!web_form_doc.is_new && !web_form_doc.in_edit_mode);
			if (df.fieldtype === "Table") {
				df.get_data = () => {
					let data = [];
					if (doc_data && doc_data[df.fieldname]) {
						return doc_data[df.fieldname];
					}
					return data;
				};

				$.each(df.fields || [], function (_i, field) {
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
});
