// Copyright (c) 2019, Frappe Technologies and contributors
// For license information, please see license.txt

frappe.ui.form.on("Notification Log", {
	refresh: function (frm) {
		if (frm.doc.attached_file) {
			frm.trigger("set_attachment");
		} else {
			frm.get_field("attachment_link").$wrapper.empty();
		}

		// `app` is auto-derived on insert but editable; load the installed-app list at runtime
		// (same pattern as Module Def.app_name) so the field and standard filter show app names.
		frappe.xcall("frappe.core.doctype.module_def.module_def.get_installed_apps").then((r) => {
			frm.set_df_property("app", "options", JSON.parse(r));
		});
	},

	open_reference_document: function (frm) {
		if (frm.doc?.link) {
			frappe.set_route(frm.doc.link);
			return;
		}
		const dt = frm.doc.document_type;
		const dn = frm.doc.document_name;
		frappe.set_route("Form", dt, dn);
	},

	set_attachment: function (frm) {
		const attachment = JSON.parse(frm.doc.attached_file);

		const $wrapper = frm.get_field("attachment_link").$wrapper;
		$wrapper.html(`
			<div class="attached-file text-medium">
				<div class="ellipsis">
					${frappe.utils.icon("paperclip", "sm")}
					<a class="attached-file-link">${attachment.name}.pdf</a>
				</div>
			</div>
		`);

		$wrapper.find(".attached-file-link").click(() => {
			const w = window.open(
				frappe.urllib.get_full_url(`/api/method/frappe.utils.print_format.download_pdf?
					doctype=${encodeURIComponent(attachment.doctype)}
					&name=${encodeURIComponent(attachment.name)}
					&format=${encodeURIComponent(attachment.print_format)}
					&lang=${encodeURIComponent(attachment.lang)}`)
			);
			if (!w) {
				frappe.msgprint(__("Please enable pop-ups"));
			}
		});
	},
});
