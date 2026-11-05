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
		frm.$wkhtmltopdf_alert?.remove();
		const count = frm.doc.__onload?.wkhtmltopdf_print_formats;
		if (
			!count ||
			!frm.doc.pdf_generator ||
			frm.doc.pdf_generator === "wkhtmltopdf" ||
			frm.is_dirty()
		)
			return;

		const generator =
			frm.doc.pdf_generator.charAt(0).toUpperCase() + frm.doc.pdf_generator.slice(1);
		const formats = (n) => (n === 1 ? __("1 print format") : __("{0} print formats", [n]));
		const title =
			count === 1
				? __("{0} still uses wkhtmltopdf.", [formats(count)])
				: __("{0} still use wkhtmltopdf.", [formats(count)]);
		const footer = [
			frappe.ui.button({
				label: __("View Formats"),
				onclick: () =>
					frappe.set_route("List", "Print Format", { pdf_generator: "wkhtmltopdf" }),
			}),
			frappe.ui.button({
				label: __("Use {0} for all", [generator]),
				variant: "solid",
				onclick: () =>
					new Promise((resolve) =>
						frappe.confirm(
							__("Switch {0} to {1}?", [formats(count), generator]),
							() =>
								resolve(
									frappe
										.xcall(
											"frappe.printing.doctype.print_settings.print_settings.follow_print_settings_pdf_generator"
										)
										.then((switched) => {
											frappe.show_alert({
												message: __("{0} switched", [formats(switched)]),
												indicator: "green",
											});
											frm.doc.__onload.wkhtmltopdf_print_formats = 0;
											frm.trigger("show_wkhtmltopdf_formats");
										})
								),
							resolve
						)
					),
			}),
		];
		frm.$wkhtmltopdf_alert = $('<div class="form-group"></div>')
			.append(frappe.ui.alert({ title, theme: "yellow", footer }))
			.insertBefore(frm.fields_dict.pdf_generator.$wrapper);
	},
});
