// Copyright (c) 2026, Frappe Technologies and contributors
// For license information, please see license.txt

frappe.ui.form.on("Security Settings", {
	refresh(frm) {
		const wrapper = frm.fields_dict.securitytxt_section.wrapper;
		if ($(wrapper).find(".security-txt-banner").length) return;

		$(wrapper)
			.find(".section-body")
			.prepend(
				frappe.ui.alert({
					theme: "yellow",
					title: __("Security.txt will be served only under HTTPS."),
					css_class: "security-txt-banner w-full",
					footer: frappe.ui.button({
						label: __("Learn more"),
						variant: "outline",
						size: "xs",
						href: "https://tools.ietf.org/html/rfc9116#section-6.7",
						attrs: { target: "_blank", rel: "noopener noreferrer" },
					}),
				})
			);
	},
});
