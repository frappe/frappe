// Copyright (c) 2018, Frappe Technologies and contributors
// For license information, please see license.txt

frappe.ui.form.on("Print Settings", {
	print_style: function (frm) {
		frappe.db.get_value("Print Style", frm.doc.print_style, "preview").then((r) => {
			if (r.message.preview) {
				frm.get_field("print_style_preview").$wrapper.html(
					`<img src="${r.message.preview}" class="img-responsive">`
				);
			} else {
				frm.get_field("print_style_preview").$wrapper.html(
					`<p style="margin: 60px 0px" class="text-center text-muted">${__(
						"No Preview"
					)}</p>`
				);
			}
		});
	},
	onload: function (frm) {
		frm.script_manager.trigger("print_style");
	},
	refresh: function (frm) {
		frm.trigger("show_wkhtmltopdf_formats");
	},
	pdf_generator: function (frm) {
		frm.trigger("show_wkhtmltopdf_formats");
	},
	show_wkhtmltopdf_formats: function (frm) {
		frm.dashboard.clear_headline();
		const count = frm.doc.__onload?.wkhtmltopdf_print_formats;
		if (!count || frm.doc.pdf_generator === "wkhtmltopdf" || frm.is_dirty()) return;

		const generator =
			frm.doc.pdf_generator.charAt(0).toUpperCase() + frm.doc.pdf_generator.slice(1);
		const $headline = frm.dashboard.set_headline(
			`<div class="flex justify-between align-center">
				<span>${__("{0} print formats still use wkhtmltopdf.", [count])}</span>
				<button class="es-button" data-size="sm">
					<span class="es-button__label">${__("Use {0} for all", [generator])}</span>
				</button>
			</div>`,
			"orange",
			true
		);
		$headline.find("button").on("click", () => {
			frappe.confirm(__("Switch {0} print formats to {1}?", [count, generator]), () =>
				frappe
					.xcall(
						"frappe.printing.doctype.print_settings.print_settings.follow_print_settings_pdf_generator"
					)
					.then((switched) => {
						frappe.show_alert({
							message: __("{0} print formats switched", [switched]),
							indicator: "green",
						});
						frm.reload_doc();
					})
			);
		});
	},
});
