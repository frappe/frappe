// Copyright (c) 2017, Frappe Technologies and contributors
// For license information, please see license.txt

const CLASSIC_BUILDER_NOTICE = __(
	"The classic builder will be removed in version 17. Convert this format to the new builder to keep editing it."
);
const is_classic_format = (doc) => doc.print_format_builder && !doc.print_format_builder_beta;
const effective_pdf_generator = (frm) => {
	const picked = !frm.get_field("pdf_generator").df.hidden && frm.doc.pdf_generator;
	return picked || frm.doc.__onload?.pdf_generator;
};

const DEPRECATED_RENDERERS = {
	WeasyPrint: __(
		"WeasyPrint is deprecated and will be removed in version 17. Switch this format to Chrome."
	),
	wkhtmltopdf: __("wkhtmltopdf is deprecated. Chrome is the supported PDF renderer."),
};

frappe.ui.form.on("Print Format", "onload", function (frm) {
	frm.add_fetch("doc_type", "module", "module");
	frm.add_fetch("report", "module", "module");

	if (frm.is_new() && !frm.doc.custom_format && !frm.doc.print_format_builder) {
		frm.set_value("print_format_builder_beta", 1);
		frm.set_value("pdf_generator", "chrome");
	}
});

frappe.ui.form.on("Print Format", {
	before_save: function (frm) {
		frm._created_this_save = frm.is_new();
	},
	after_save: function (frm) {
		if (
			frm._created_this_save &&
			frm.doc.print_format_builder_beta &&
			!frm.doc.custom_format &&
			frm.doc.print_format_for !== "Report"
		) {
			frappe.set_route("print-format-builder-beta", frm.doc.name);
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
		frm.trigger("set_pdf_generator_options");
		frm.trigger("set_chrome_for_builder");
		frm.trigger("show_renderer_notice");
	},
	render_buttons: function (frm) {
		frm.page.clear_inner_toolbar();
		if (!frm.is_new() && frm.doc.print_format_for === "DocType") {
			const renders_from_file = frm.doc.__onload?.renders_from_file;
			if (!frm.doc.custom_format && !renders_from_file) {
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
			const can_convert = frm.doc.standard !== "Yes" || frappe.boot.developer_mode;
			if (is_classic_format(frm.doc) && !renders_from_file) {
				frm.add_custom_button(__("Convert to new builder"), function () {
					frappe.printing.convert_to_builder(frm.doc);
				});
			}
			if (frm.doc.classic_format_data && can_convert) {
				frm.add_custom_button(__("Restore classic layout"), function () {
					frappe.confirm(
						__(
							"This restores the classic layout backup and discards the converted layout. Continue?"
						),
						() => {
							frappe
								.xcall(
									"frappe.printing.doctype.print_format.print_format.restore_classic_layout",
									{ name: frm.doc.name }
								)
								.then(() => frm.reload_doc());
						}
					);
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
	set_pdf_generator_options: function (frm) {
		const df = frappe.meta.get_docfield("Print Format", "pdf_generator", frm.doc.name);
		const all_options = (df?.options || "").split("\n").filter(Boolean);
		const keep_weasyprint = !frm.is_new();
		const options = all_options.filter((o) => o !== "WeasyPrint" || keep_weasyprint);
		frm.set_df_property("pdf_generator", "options", options.join("\n"));
	},
	show_renderer_notice: function (frm) {
		frm.dashboard.clear_headline();
		const notices = [
			is_classic_format(frm.doc) && CLASSIC_BUILDER_NOTICE,
			DEPRECATED_RENDERERS[effective_pdf_generator(frm)],
		].filter(Boolean);
		if (notices.length) frm.dashboard.set_headline(notices.join(" "), "orange");
	},
	pdf_generator: function (frm) {
		frm.trigger("show_renderer_notice");
	},
	custom_format: function (frm) {
		var value = frm.doc.custom_format ? 0 : 1;
		frm.set_value("align_labels_right", value);
		frm.set_value("show_section_headings", value);
		frm.set_value("line_breaks", value);
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
		const should_force_chrome =
			is_builder &&
			frm.is_new() &&
			!is_custom &&
			!["Typst", "WeasyPrint"].includes(frm.doc.pdf_generator);
		if (should_force_chrome) {
			frm.set_value("pdf_generator", "chrome");
		}
		frm.toggle_display("pdf_generator", !(is_builder && !is_custom));
	},
	doc_type: function (frm) {
		frm.trigger("hide_absolute_value_field");
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
			frm.set_value("standard", "No");
			frm.set_value("custom_format", 1);
		}
	},
	hide_absolute_value_field: function (frm) {
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
