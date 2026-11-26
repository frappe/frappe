// Copyright (c) 2022, Frappe Technologies and contributors
// For license information, please see license.txt

frappe.ui.form.on("Report", {
	refresh: function (frm) {
		const can_write = frm.perm[0].write;
		if (frm.doc.is_standard === "Yes" && !frappe.boot.developer_mode) {
			// make the document read-only
			frm.disable_form();
		} else {
			frm.enable_save();
		}

		let doc = frm.doc;
		if (!doc.__islocal) {
			frm.add_custom_button(__("Show Report"), function () {
				switch (doc.report_type) {
					case "Report Builder":
						frappe.set_route("List", doc.ref_doctype, "Report", doc.name);
						break;
					case "Query Report":
						frappe.set_route("query-report", doc.name);
						break;
					case "Script Report":
						frappe.set_route("query-report", doc.name);
						break;
					case "Custom Report":
						frappe.set_route("query-report", doc.name);
						break;
				}
			});
		}

		if (doc.is_standard === "Yes" && !frappe.boot.developer_mode && can_write) {
			frm.add_custom_button(__("Set Print Defaults"), () =>
				frm.trigger("set_print_defaults")
			);
		}

		if (doc.is_standard === "Yes" && can_write) {
			frm.add_custom_button(
				doc.disabled ? __("Enable Report") : __("Disable Report"),
				function () {
					frm.call("toggle_disable", {
						disable: doc.disabled ? 0 : 1,
					}).then(() => {
						frm.reload_doc();
					});
				}
			);
		}

		frm.set_query("ref_doctype", () => {
			return {
				filters: {
					istable: 0,
				},
			};
		});

		frm.set_query("default_print_format", () => {
			return {
				filters: {
					print_format_for: "Report",
					report: frm.doc.name,
					disabled: 0,
				},
			};
		});

		frm.set_query("default_letter_head", () => {
			const filters = {
				letter_head_for: "Report",
				disabled: 0,
			};

			if (frm.doc.is_standard === "Yes") {
				filters.standard = "Yes";
			}

			return { filters };
		});
	},

	set_print_defaults(frm) {
		const dialog = new frappe.ui.Dialog({
			title: __("Set Print Defaults"),
			fields: [
				{
					fieldname: "print_format",
					fieldtype: "Link",
					label: __("Default Print Format"),
					options: "Print Format",
					default: frm.doc.default_print_format,
					get_query: () => ({
						filters: { print_format_for: "Report", report: frm.doc.name, disabled: 0 },
					}),
				},
				{
					fieldname: "letter_head",
					fieldtype: "Link",
					label: __("Default Letter Head"),
					options: "Letter Head",
					default: frm.doc.default_letter_head,
					get_query: () => ({ filters: { letter_head_for: "Report", disabled: 0 } }),
				},
			],
			primary_action_label: __("Save"),
			primary_action: (values) => {
				frm.call("set_print_defaults", values).then(() => {
					dialog.hide();
					frm.reload_doc();
				});
			},
		});
		dialog.show();
	},

	ref_doctype: function (frm) {
		if (frm.doc.ref_doctype) {
			frm.trigger("set_doctype_roles");
		}
	},

	set_doctype_roles: function (frm) {
		return frm.call("set_doctype_roles").then(() => {
			frm.refresh_field("roles");
		});
	},
});
