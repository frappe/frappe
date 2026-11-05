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
	after_save: function (frm) {
		const count = frm.doc.__onload?.wkhtmltopdf_print_formats;
		if (!count || !frm.doc.pdf_generator || frm.doc.pdf_generator === "wkhtmltopdf") return;

		const generator =
			frm.doc.pdf_generator.charAt(0).toUpperCase() + frm.doc.pdf_generator.slice(1);
		const formats = (n) => (n === 1 ? __("1 print format") : __("{0} print formats", [n]));
		const message =
			count === 1
				? __("{0} still uses wkhtmltopdf.", [formats(count)])
				: __("{0} still use wkhtmltopdf.", [formats(count)]);
		const action = (label, onclick) =>
			$(`<button class="next-action"><span>${label}</span></button>`).on("click", onclick);
		const $toast = frappe.show_alert(
			{
				message,
				indicator: "orange",
				body: $('<div class="next-action-container"></div>').append(
					action(__("View"), () =>
						frappe.set_route("List", "Print Format", { pdf_generator: "wkhtmltopdf" })
					),
					action(__("Switch All"), () =>
						frappe.confirm(__("Switch {0} to {1}?", [formats(count), generator]), () =>
							frappe
								.xcall(
									"frappe.printing.doctype.print_settings.print_settings.follow_print_settings_pdf_generator"
								)
								.then((switched) => {
									$toast.remove();
									frm.doc.__onload.wkhtmltopdf_print_formats = 0;
									frappe.show_alert({
										message: __("{0} switched", [formats(switched)]),
										indicator: "green",
									});
								})
						)
					)
				),
			},
			15
		);
	},
});
