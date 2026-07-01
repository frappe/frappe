// Copyright (c) 2017, Frappe Technologies and contributors
// For license information, please see license.txt

frappe.ui.form.on("Print Format", "onload", function (frm) {
	frm.add_fetch("doc_type", "module", "module");
	frm.add_fetch("report", "module", "module");

	// For new non-custom formats: default to Print Format Builder Beta + Chrome PDF
	if (frm.is_new() && !frm.doc.custom_format) {
		frm.set_value("print_format_builder_beta", 1);
		frm.set_value("pdf_generator", "chrome");
	}
});

frappe.ui.form.on("Print Format", {
	refresh: function (frm) {
		frm.set_intro("");
		frm.toggle_enable(["html", "doc_type", "module"], false);
		if (frappe.session.user === "Administrator" || frm.doc.standard === "No") {
			frm.toggle_enable(["html", "doc_type", "module"], true);
			frm.enable_save();
		}

		if (frm.doc.standard === "Yes" && frappe.session.user !== "Administrator") {
			frm.set_intro(__("Please duplicate this to make changes"));
		}
		frm.trigger("render_buttons");
		frm.toggle_display("standard", frappe.boot.developer_mode);
		frm.trigger("hide_absolute_value_field");
		frm.trigger("set_chrome_for_builder");
	},
	render_buttons: function (frm) {
		frm.page.clear_inner_toolbar();
		if (!frm.is_new() && frm.doc.print_format_for === "DocType") {
			if (!frm.doc.custom_format) {
				frm.add_custom_button(__("Edit Format"), function () {
					if (!frm.doc.doc_type) {
						frappe.msgprint(__("Please select DocType first"));
						return;
					}
					if (frm.doc.print_format_builder_beta) {
						frappe.set_route("print-format-builder", frm.doc.name);
					} else {
						frappe.set_route("print-format-builder-classic", frm.doc.name);
					}
				});
			}
			if (frappe.model.can_write("Customize Form")) {
				frappe.model.with_doctype(frm.doc.doc_type, function () {
					let current_format = frappe.get_meta(frm.doc.doc_type).default_print_format;
					if (current_format == frm.doc.name) {
						return;
					}

					frm.add_custom_button(__("Set as Default"), function () {
						frappe.call({
							method: "frappe.printing.doctype.print_format.print_format.make_default",
							args: {
								name: frm.doc.name,
							},
							callback: function () {
								frm.refresh();
							},
						});
					});
				});
			}
		}
	},
	custom_format: function (frm) {
		var value = frm.doc.custom_format ? 0 : 1;
		frm.set_value("align_labels_right", value);
		frm.set_value("show_section_headings", value);
		frm.set_value("line_breaks", value);
		// Custom HTML formats can't use the builder — clear the flag
		if (frm.doc.custom_format) {
			frm.set_value("print_format_builder_beta", 0);
		}
		frm.trigger("render_buttons");
		frm.trigger("set_chrome_for_builder");
	},
	print_format_builder_beta: function (frm) {
		frm.trigger("set_chrome_for_builder");
	},
	set_chrome_for_builder: function (frm) {
		const is_builder = frm.doc.print_format_builder_beta;
		const is_custom = frm.doc.custom_format;
		const should_force_chrome = is_builder && (frm.is_new() || !is_custom);
		if (should_force_chrome) {
			frm.set_value("pdf_generator", "chrome");
		}
		frm.set_df_property("pdf_generator", "read_only", should_force_chrome ? 1 : 0);
	},
	doc_type: function (frm) {
		frm.trigger("hide_absolute_value_field");
	},
	print_format_for: function (frm) {
		if (frm.doc.print_format_for === "Report") {
			frm.set_value("custom_format", 1);
		}
	},
	hide_absolute_value_field: function (frm) {
		// TODO: make it work with frm.doc.doc_type
		// Problem: frm isn't updated in some random cases
		const doctype = locals[frm.doc.doctype][frm.doc.name].doc_type;
		if (doctype) {
			frappe.model.with_doctype(doctype, () => {
				const meta = frappe.get_meta(doctype);
				const has_int_float_currency_field = meta.fields.filter((df) =>
					["Int", "Float", "Currency"].includes(df.fieldtype)
				);
				frm.toggle_display("absolute_value", has_int_float_currency_field.length);
			});
		}
	},
});
