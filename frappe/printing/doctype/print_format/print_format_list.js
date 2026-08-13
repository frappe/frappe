frappe.listview_settings["Print Format"] = {
	add_fields: ["print_format_builder_beta", "custom_format", "print_format_for", "standard"],

	// Builder formats open in the builder; everything else (custom HTML, JS, raw,
	// Report, Print Designer) keeps the form. Standard builder formats open in the
	// builder only in developer mode — production users get the form and its
	// "Please duplicate this to make changes" guidance.
	get_form_link(doc) {
		if (
			doc.print_format_builder_beta &&
			!doc.custom_format &&
			doc.print_format_for !== "Report" &&
			(doc.standard !== "Yes" || frappe.boot.developer_mode)
		) {
			return `/desk/print-format-builder/${encodeURIComponent(doc.name)}`;
		}
		return `/desk/print-format/${encodeURIComponent(doc.name)}`;
	},

	primary_action() {
		const dev = !!frappe.boot.developer_mode;
		const fields = [
			{
				label: __("Print Format For"),
				fieldname: "print_format_for",
				fieldtype: "Select",
				options: "DocType\nReport",
				default: "DocType",
				reqd: 1,
			},
			{
				label: __("DocType"),
				fieldname: "doc_type",
				fieldtype: "Link",
				options: "DocType",
				depends_on: 'eval:doc.print_format_for !== "Report"',
				mandatory_depends_on: 'eval:doc.print_format_for !== "Report"',
			},
			{
				label: __("Report"),
				fieldname: "report",
				fieldtype: "Link",
				options: "Report",
				depends_on: 'eval:doc.print_format_for === "Report"',
				mandatory_depends_on: 'eval:doc.print_format_for === "Report"',
			},
			{
				label: __("Name"),
				fieldname: "print_format_name",
				fieldtype: "Data",
				reqd: 1,
			},
			{
				// Reports have no visual layout, so they are always HTML
				label: __("Start with"),
				fieldname: "start_with",
				fieldtype: "Select",
				options: "Builder\nHTML",
				default: "Builder",
				depends_on: 'eval:doc.print_format_for !== "Report"',
				description: __("Builder is visual. HTML is hand-written."),
			},
		];

		// Standard formats are saved as files in an app — a developer-only concern
		if (dev) {
			fields.push(
				{
					label: __("Standard"),
					fieldname: "standard",
					fieldtype: "Check",
					default: 0,
					description: __("Ship as files in an app, tracked in git."),
				},
				{
					label: __("Module"),
					fieldname: "module",
					fieldtype: "Link",
					options: "Module Def",
					depends_on: "standard",
					mandatory_depends_on: "standard",
				}
			);
		}

		const dialog = new frappe.ui.Dialog({
			title: __("New Print Format"),
			fields,
			primary_action_label: __("Create"),
			primary_action(values) {
				const for_report = values.print_format_for === "Report";
				const use_html = for_report || values.start_with === "HTML";

				const doc = { doctype: "Print Format", name: values.print_format_name };
				if (for_report) {
					doc.print_format_for = "Report";
					doc.report = values.report;
				} else {
					doc.doc_type = values.doc_type;
				}
				if (use_html) {
					// a custom format can't save with empty HTML, so seed a starter
					doc.custom_format = 1;
					doc.html = `<div class="print-format">\n\t<h3>${frappe.utils.escape_html(
						values.print_format_name
					)}</h3>\n</div>`;
				} else {
					doc.print_format_builder_beta = 1;
				}
				if (values.standard) {
					doc.standard = "Yes";
					if (values.module) doc.module = values.module;
				}

				return frappe.db.insert(doc).then((saved) => {
					dialog.hide();
					// only builder formats open the builder; HTML/Report go to the form
					if (doc.print_format_builder_beta) {
						frappe.set_route("print-format-builder", saved.name);
					} else {
						frappe.set_route("Form", "Print Format", saved.name);
					}
				});
			},
		});
		dialog.show();
	},
};
