// Copyright (c) 2026, Frappe Technologies and contributors
// For license information, please see license.txt

frappe.ui.form.on("Web Crawl", {
	setup(frm) {
		const reload = frappe.utils.throttle(() => frm.reload_doc(), 1000);
		frappe.realtime.on("web_crawl_progress", ({ web_crawl }) => {
			if (web_crawl === frm.doc.name) reload();
		});
	},
	refresh(frm) {
		if (frm.is_new()) return;
		// Every field is read-only or set once, so a saved crawl has nothing to save.
		frm.disable_save();

		if (frm.doc.stopped_reason === "Time limit") {
			frm.set_intro(
				__(
					"This crawl stopped at the maximum crawl time after {0} pages. Raise Maximum crawl time in Web Crawl Settings to read more.",
					[frm.doc.pages_crawled]
				),
				"orange"
			);
		}
		if (frm.doc.stopped_reason === "robots.txt too large") {
			frm.set_intro(
				__(
					"This site's robots.txt is larger than Maximum robots.txt size, so no page was read. Raise it in Web Crawl Settings to crawl this site."
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
			if (frm.doc.status === "Completed") {
				frm.change_custom_button_type(__("View Results"), null, "primary");
			}
		}
		frm.toggle_display("results_html", is_manager);
		if (is_manager) render_results(frm);
	},
});

function render_results(frm) {
	// One list per form, so the many refreshes of a load never stack lists.
	frm.results_list ??= make_results_list(frm);
	frm.results_list.then((list) => list.refresh());
}

function make_results_list(frm) {
	const wrapper = frm.fields_dict.results_html.$wrapper.empty().addClass("web-crawl-results");
	return Promise.all([
		frappe.require("embedded_list.bundle.js"),
		// Loads the result list settings, whose indicator labels each page.
		new Promise((resolve) => frappe.model.with_doctype("Web Crawl Result", resolve)),
	]).then(() => {
		const indicator = frappe.listview_settings["Web Crawl Result"].get_indicator;
		return new frappe.ui.EmbeddedList({
			wrapper,
			empty_message: __("No pages read yet."),
			columns: [
				{
					label: __("Page"),
					fieldname: "title",
					type: "link",
					text: (row) => row.title || row.url,
					route: (row) => ["Form", "Web Crawl Result", row.name],
				},
				{
					label: __("Result"),
					render: (row) => {
						const [label, color] = indicator(row) || [];
						return label ? frappe.ui.badge.html({ label, theme: color }) : "";
					},
				},
			],
			get_page: ({ start, page_length, txt }) =>
				frappe.db.get_list("Web Crawl Result", {
					filters: { web_crawl: frm.docname },
					or_filters: txt
						? [
								["title", "like", `%${txt}%`],
								["url", "like", `%${txt}%`],
						  ]
						: undefined,
					fields: ["name", "title", "url", "error", "change_status"],
					order_by: "creation asc",
					start,
					limit: page_length,
				}),
		});
	});
}
