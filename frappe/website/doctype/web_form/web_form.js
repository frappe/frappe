frappe.ui.form.on("Web Form", {
	refresh: function (frm) {
		// show is-standard only if developer mode
		frm.get_field("is_standard").toggle(frappe.boot.developer_mode);

		if (frm.doc.is_standard && !frappe.boot.developer_mode) {
			frm.set_read_only();
			frm.disable_save();
		}
		render_list_settings_message(frm);

		frm.trigger("set_fields");
		frm.trigger("add_get_fields_button");
		frm.trigger("add_publish_button");
	},

	login_required: function (frm) {
		render_list_settings_message(frm);
	},

	validate: function (frm) {
		if (!frm.doc.login_required) {
			frm.set_value("allow_multiple", 0);
			frm.set_value("allow_edit", 0);
			frm.set_value("show_list", 0);
		}

		!frm.doc.allow_multiple && frm.set_value("allow_delete", 0);
		frm.doc.allow_multiple && frm.set_value("show_list", 1);

		if (!frm.doc.web_form_fields) {
			frm.scroll_to_field("web_form_fields");
			frappe.throw(__("Atleast one field is required in Web Form Fields Table"));
		}
	},

	add_publish_button(frm) {
		frm.add_custom_button(frm.doc.published ? __("Unpublish") : __("Publish"), () => {
			frm.set_value("published", !frm.doc.published);
			frm.save();
		});
	},

	add_get_fields_button(frm) {
		frm.add_custom_button(__("Get Fields"), () => {
			let webform_fieldtypes = frappe.meta
				.get_field("Web Form Field", "fieldtype")
				.options.split("\n");

			let added_fields = (frm.doc.fields || []).map((d) => d.fieldname);

			get_fields_for_doctype(frm.doc.doc_type).then((fields) => {
				for (let df of fields) {
					if (
						webform_fieldtypes.includes(df.fieldtype) &&
						!added_fields.includes(df.fieldname) &&
						!df.hidden
					) {
						frm.add_child("web_form_fields", {
							fieldname: df.fieldname,
							label: df.label,
							fieldtype: df.fieldtype,
							options: df.options,
							reqd: df.reqd,
							default: df.default,
							read_only: df.read_only,
							depends_on: df.depends_on,
							mandatory_depends_on: df.mandatory_depends_on,
							read_only_depends_on: df.read_only_depends_on,
						});
					}
				}
				frm.refresh_field("web_form_fields");
				frm.scroll_to_field("web_form_fields");
			});
		});
	},

	set_fields(frm) {
		let doc = frm.doc;

		let update_options = (options) => {
			[frm.fields_dict.web_form_fields.grid, frm.fields_dict.list_columns.grid].forEach(
				(obj) => {
					obj.update_docfield_property("fieldname", "options", options);
				}
			);
		};

		if (!doc.doc_type) {
			update_options([]);
			frm.set_df_property("amount_field", "options", []);
			return;
		}

		update_options([`Fetching fields from ${doc.doc_type}...`]);

		get_fields_for_doctype(doc.doc_type).then((fields) => {
			let as_select_option = (df) => ({
				label: df.label + " (" + df.fieldtype + ")",
				value: df.fieldname,
			});
			update_options(fields.map(as_select_option));

			let currency_fields = fields
				.filter((df) => ["Currency", "Float"].includes(df.fieldtype))
				.map(as_select_option);
			if (!currency_fields.length) {
				currency_fields = [
					{
						label: `No currency fields in ${doc.doc_type}`,
						value: "",
						disabled: true,
					},
				];
			}
			frm.set_df_property("amount_field", "options", currency_fields);
		});
	},

	title: function (frm) {
		if (frm.doc.__islocal) {
			var page_name = frm.doc.title.toLowerCase().replace(/ /g, "-");
			frm.set_value("route", page_name);
		}
	},

	doc_type: function (frm) {
		frm.trigger("set_fields");
	},

	allow_multiple: function (frm) {
		frm.doc.allow_multiple && frm.set_value("show_list", 1);
	},
});

frappe.ui.form.on("Web Form List Column", {
	fieldname: function (frm, doctype, name) {
		let doc = frappe.get_doc(doctype, name);
		let df = frappe.meta.get_docfield(frm.doc.doc_type, doc.fieldname);
		if (!df) return;
		doc.fieldtype = df.fieldtype;
		doc.label = df.label;
		frm.refresh_field("list_columns");
	},
});

frappe.ui.form.on("Web Form Field", {
	fieldtype: function (frm, doctype, name) {
		var doc = frappe.get_doc(doctype, name);
		if (["Section Break", "Column Break", "Page Break"].includes(doc.fieldtype)) {
			doc.fieldname = "";
			doc.options = "";
			frm.refresh_field("web_form_fields");
		}
	},
	fieldname: function (frm, doctype, name) {
		let doc = frappe.get_doc(doctype, name);
		let df = frappe.meta.get_docfield(frm.doc.doc_type, doc.fieldname);
		if (!df) return;

		doc.label = df.label;
		doc.fieldtype = df.fieldtype;
		doc.options = df.options;
		doc.reqd = df.reqd;
		doc.default = df.default;
		doc.read_only = df.read_only;
		doc.depends_on = df.depends_on;
		doc.mandatory_depends_on = df.mandatory_depends_on;
		doc.read_only_depends_on = df.read_only_depends_on;

		frm.refresh_field("web_form_fields");
	},
});

function get_fields_for_doctype(doctype) {
	return new Promise((resolve) => frappe.model.with_doctype(doctype, resolve)).then(() => {
		return frappe.meta.get_docfields(doctype).filter((df) => {
			return (
				(frappe.model.is_value_type(df.fieldtype) &&
					!["lft", "rgt"].includes(df.fieldname)) ||
				["Table", "Table Multiselect"].includes(df.fieldtype)
			);
		});
	});
}

function render_list_settings_message(frm) {
	// render list setting message
	if (frm.fields_dict["list_setting_message"] && !frm.doc.login_required) {
		const switch_to_form_settings_tab = `
			<span class="bold pointer" title="${__("Switch to Form Settings Tab")}">
				${__("Form Settings Tab")}
			</span>
		`;
		$(frm.fields_dict["list_setting_message"].wrapper)
			.html(
				$(
					`<div class="form-message blue">
					${__(
						"Login is required to see web form list view. Enable <code>login_required</code> from {0} to see list settings",
						[switch_to_form_settings_tab]
					)}
				</div>`
				)
			)
			.find("span")
			.click(() => frm.scroll_to_field("login_required"));
	} else {
		$(frm.fields_dict["list_setting_message"].wrapper).empty();
	}
}
