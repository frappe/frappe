// Copyright (c) 2026, Frappe Technologies and contributors
// For license information, please see license.txt

frappe.ui.form.on("Security Settings", {
	refresh(frm) {
		const wrapper = frm.fields_dict.securitytxt_section.wrapper;
		if ($(wrapper).find(".security-txt-banner").length) return;

		$(wrapper)
			.find(".section-body")
			.prepend(
				`<div class="alert alert-warning border d-flex justify-content-between align-items-center security-txt-banner" style="flex: 0 0 100%; max-width: 100%; border-color: var(--border-color);">
					<span>${__("Security.txt will be served only under HTTPS.")}</span>
					<a href="https://tools.ietf.org/html/rfc9116#section-6.7" target="_blank" class="btn btn-xs btn-secondary">${__(
						"Learn more"
					)}</a>
				</div>`
			);
	},
});
