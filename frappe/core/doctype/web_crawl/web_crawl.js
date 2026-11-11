// Copyright (c) 2026, Frappe Technologies and contributors
// For license information, please see license.txt

frappe.ui.form.on("Web Crawl", {
	refresh(frm) {
		if (frm.is_new()) return;

		if (frm.doc.status === "Queued" && !frm.doc.background_task) {
			frm.page.set_primary_action(__("Start"), () =>
				frm.call("start").then(() => frm.reload_doc())
			);
		}
		if (["Queued", "Running"].includes(frm.doc.status) && frm.doc.background_task) {
			frm.add_custom_button(__("Stop"), () =>
				frappe.confirm(__("Stop this crawl? Pages read so far are kept."), () =>
					frm.call("stop").then(() => frm.reload_doc())
				)
			);
		}
		if (frm.doc.pages_crawled) {
			frm.add_custom_button(__("View Pages"), () =>
				frappe.set_route("List", "Web Crawl Page", { web_crawl: frm.doc.name })
			);
		}
	},
});
