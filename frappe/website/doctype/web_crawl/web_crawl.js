// Copyright (c) 2026, Frappe Technologies and contributors
// For license information, please see license.txt

frappe.ui.form.on("Web Crawl", {
	refresh(frm) {
		if (frm.is_new()) return;

		if (frm.doc.stopped_reason === "Time limit") {
			frm.set_intro(
				__(
					"This crawl stopped at the maximum crawl time after {0} pages. Raise Maximum crawl time in Web Crawl Settings to read more.",
					[frm.doc.pages_crawled]
				),
				"orange"
			);
		}
		if (frm.doc.stopped_reason === "Rate limited") {
			frm.set_intro(
				__(
					"This crawl stopped after {0} pages because the site asked for fewer requests. Try again later, or lower Concurrent requests in Web Crawl Settings.",
					[frm.doc.pages_crawled]
				),
				"orange"
			);
		}

		// Readers through the reference document can neither stop the crawl nor list its results.
		const is_manager =
			frm.doc.owner === frappe.session.user || frappe.perm.has_perm(frm.doctype, 0, "write");
		const is_running = ["Queued", "Running"].includes(frm.doc.status);
		if (is_manager && is_running && frm.doc.background_task) {
			frm.add_custom_button(__("Stop"), () =>
				frappe.confirm(__("Stop this crawl? Pages read so far are kept."), () =>
					// By name: the job keeps updating the crawl, so the form's copy may be out of date.
					frappe
						.xcall("run_doc_method", {
							dt: frm.doctype,
							dn: frm.docname,
							method: "stop",
						})
						.then(
							() => frm.reload_doc(),
							() => frm.reload_doc()
						)
				)
			);
		}
		if (is_manager && frm.doc.pages_crawled) {
			frm.add_custom_button(__("View Results"), () =>
				frappe.set_route("List", "Web Crawl Result", { web_crawl: frm.doc.name })
			);
		}
	},
});
