// Copyright (c) 2017, Frappe Technologies and contributors
// For license information, please see license.txt

frappe.ui.form.on("Print Format", "onload", function (frm) {
	frm.add_fetch("doc_type", "module", "module");
	frm.add_fetch("report", "module", "module");

	if (frm.is_new() && !frm.doc.custom_format) {
		frm.set_value("print_format_builder_beta", 1);
	}
});

frappe.ui.form.on("Print Format", {
	before_save: function (frm) {
		frm._created_this_save = frm.is_new();
	},
	after_save: function (frm) {
		// A brand-new builder format has nothing to do on the form — take the
		// user straight to the builder. Custom/Report formats stay here.
		if (
			frm._created_this_save &&
			frm.doc.print_format_builder_beta &&
			!frm.doc.custom_format &&
			frm.doc.print_format_for !== "Report"
		) {
			frappe.set_route("print-format-builder", frm.doc.name);
		}
		frm._created_this_save = false;
	},
	refresh: function (frm) {
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
		frm.trigger("render_html_preview");
	},
	html: (frm) => frm.events.queue_html_preview(frm),
	css: (frm) => frm.events.queue_html_preview(frm),
	raw_printing: (frm) => frm.events.queue_html_preview(frm),
	queue_html_preview(frm) {
		clearTimeout(frm._html_preview_timer);
		frm._html_preview_timer = setTimeout(() => frm.trigger("render_html_preview"), 600);
	},
	async render_html_preview(frm) {
		const field = frm.get_field("html_preview");
		const { custom_format, raw_printing, print_format_for, doc_type } = frm.doc;
		const request = (frm._html_preview_request = (frm._html_preview_request || 0) + 1);
		if (
			!frm.has_perm("write") ||
			!custom_format ||
			raw_printing ||
			print_format_for !== "DocType" ||
			!doc_type
		) {
			field.$wrapper.empty();
			return;
		}
		await frappe.model.with_doctype(doc_type);
		let name = doc_type;
		if (!frappe.get_meta(doc_type).issingle) {
			const [sample] = await frappe.db.get_list(doc_type, {
				limit: 1,
				order_by: "modified desc",
			});
			name = sample?.name;
		}
		if (request !== frm._html_preview_request) return;
		if (!name) {
			field.html(
				`<p class="text-muted">${__("Create a {0} to see a preview.", [__(doc_type)])}</p>`
			);
			return;
		}
		const out = await frappe.xcall("frappe.www.printview.get_unsaved_format_preview", {
			print_format: frm.doc,
			doctype: doc_type,
			name,
		});
		if (request !== frm._html_preview_request) return;
		frappe.ui.show_print_preview(field, out);
	},
	render_buttons: function (frm) {
		frm.page.clear_inner_toolbar();
		if (!frm.is_new() && frm.doc.print_format_for === "DocType") {
			if (!frm.doc.custom_format && !frm.doc.__onload?.renders_from_file) {
				frm.add_custom_button(__("Edit Format"), function () {
					if (!frm.doc.doc_type) {
						frappe.msgprint(__("Please select DocType first"));
						return;
					}
					frappe.set_route("print-format-builder", frm.doc.name);
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
		frm.trigger("queue_html_preview");
	},
	doc_type: function (frm) {
		frm.trigger("hide_absolute_value_field");
		frm.trigger("queue_html_preview");
	},
	disabled: function (frm) {
		if (!frm.doc.disabled || !frm.doc.doc_type) return;

		frappe.model.with_doctype(frm.doc.doc_type, () => {
			if (frappe.get_meta(frm.doc.doc_type).default_print_format !== frm.doc.name) return;

			frappe.confirm(
				__(
					"{0} is the default print format for {1}. Disabling it will remove it as the default. Do you want to continue?",
					[frm.doc.name.bold(), frm.doc.doc_type.bold()]
				),
				null,
				() => frm.set_value("disabled", 0)
			);
		});
	},
	print_format_for: function (frm) {
		if (frm.doc.print_format_for === "Report") {
			frm.set_value("custom_format", 1);
		}
		frm.trigger("queue_html_preview");
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
