// Copyright (c) 2017, Frappe Technologies and contributors
// For license information, please see license.txt

// NOTE: Do not use frappe.model.with_doctype() in this file since it will sync
// outdated print format data to locals, interfering with this form.

frappe.ui.form.on("Print Format", "onload", function (frm) {
	frm.add_fetch("doc_type", "module", "module");
	frm.add_fetch("report", "module", "module");
});

frappe.ui.form.on("Print Format", {
	refresh: function (frm) {
		if (
			!frm.is_dirty() &&
			frm.doc.standard === "Yes" &&
			!(frm.doc.html || frm.doc.css || frm.doc.raw_commands)
		) {
			frm.reload_doc();
			return;
		}

		frm.set_intro("");
		frm.toggle_enable(["doc_type", "module"], false);
		if (frappe.session.user === "Administrator" || frm.doc.standard === "No") {
			frm.toggle_enable(["doc_type", "module"], true);
			frm.enable_save();
		}

		if (frm.doc.standard === "Yes" && frappe.session.user !== "Administrator") {
			frm.set_intro(__("Please duplicate this to make changes"));
		}
		frm.trigger("render_buttons");
		frm.toggle_display("standard", frappe.boot.developer_mode);
		frm.trigger("hide_absolute_value_field");
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
						frappe.set_route("print-format-builder-beta", frm.doc.name);
					} else {
						frappe.set_route("print-format-builder", frm.doc.name);
					}
				});
			}
			if (frappe.model.can_write("Customize Form")) {
				if (!frm.doc.__onload.is_default_print_format) {
					frm.add_custom_button(__("Set as Default"), function () {
						frappe.call({
							method: "frappe.printing.doctype.print_format.print_format.make_default",
							args: {
								name: frm.doc.name,
							},
							callback: function () {
								frm.reload_doc();
							},
						});
					});
				}
			}
		}
	},
	custom_format: function (frm) {
		var value = frm.doc.custom_format ? 0 : 1;
		frm.set_value("align_labels_right", value);
		frm.set_value("show_section_headings", value);
		frm.set_value("line_breaks", value);
		frm.trigger("render_buttons");
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
			frappe
				.xcall("frappe.printing.doctype.print_format.print_format.has_number_field", {
					doctype: doctype,
				})
				.then((has_number_field) => {
					frm.toggle_display("absolute_value", has_number_field);
				});
		}
	},
});
