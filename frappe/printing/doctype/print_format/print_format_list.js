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
	},

	primary_action() {
		const dialog = new frappe.ui.Dialog({
			title: __("New Print Format"),
			fields: [
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
			],
			primary_action_label: __("Create"),
			primary_action(values) {
				const for_report = values.print_format_for === "Report";
				// custom_format is left for the server's before_save — setting it here
				// would trip the "HTML is required" check before any HTML exists
				const doc = for_report
					? {
							doctype: "Print Format",
							name: values.print_format_name,
							print_format_for: "Report",
							report: values.report,
					  }
					: {
							doctype: "Print Format",
							name: values.print_format_name,
							doc_type: values.doc_type,
							print_format_builder_beta: 1,
					  };
				frappe.db.insert(doc).then((saved) => {
					dialog.hide();
					if (for_report) {
						frappe.set_route("Form", "Print Format", saved.name);
					} else {
						frappe.set_route("print-format-builder", saved.name);
					}
				});
			},
		});
		dialog.show();
	},
};
