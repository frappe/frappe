// Copyright (c) 2019, Frappe Technologies and contributors
// For license information, please see license.txt

frappe.ui.form.on("Notification Settings", {
	onload: (frm) => {
		frm.set_query("subscribed_documents", () => {
			return {
				filters: {
					istable: 0,
				},
			};
		});
	},

	refresh: (frm) => {
		if (frappe.user.has_role("System Manager")) {
			frm.add_custom_button(__("Go to Notification Settings List"), () => {
				frappe.set_route("List", "Notification Settings");
			});
		}
		setup_email_types_editor(frm);
	},
});

function setup_email_types_editor(frm) {
	const wrapper = frm.fields_dict.email_notification_types_html?.wrapper;
	if (!wrapper) return;

	const table_fieldname = "email_notification_types";
	const value_fieldname = "notification_type";
	const child_doctype = frappe.meta.get_docfield(frm.doctype, table_fieldname).options;

	const get_selected = () => (frm.doc[table_fieldname] || []).map((row) => row[value_fieldname]);

	if (frm.email_types_multicheck) {
		// already built — just re-sync checked state (e.g. after reload)
		frm.email_types_multicheck.selected_options = get_selected();
		frm.email_types_multicheck.refresh_input();
		return;
	}

	$(wrapper).empty();
	$(`
		<p class="text-muted small mb-2">
			${__(
				"Choose which notification types are emailed to you. Unchecked types still show as in-app notifications."
			)}
		</p>
	`).appendTo(wrapper);

	frm.email_types_multicheck = frappe.ui.form.make_control({
		parent: wrapper,
		render_input: true,
		df: {
			fieldname: table_fieldname,
			fieldtype: "MultiCheck",
			select_all: true,
			columns: 4,
			get_data: () =>
				frappe
					.xcall(
						"frappe.desk.doctype.notification_settings.notification_settings.get_emailable_notification_types"
					)
					.then((types) => {
						const selected = get_selected();
						return types.map((t) => ({
							label: __(t),
							value: t,
							checked: selected.includes(t),
						}));
					}),
			on_change: () => {
				set_types_in_table(frm, table_fieldname, value_fieldname, child_doctype);
				frm.dirty();
			},
		},
	});
}

function set_types_in_table(frm, table_fieldname, value_fieldname, child_doctype) {
	const checked = frm.email_types_multicheck.get_checked_options();
	const rows = frm.doc[table_fieldname] || [];

	rows.forEach((row) => {
		if (!checked.includes(row[value_fieldname])) {
			frappe.model.clear_doc(row.doctype, row.name);
		}
	});
	checked.forEach((type) => {
		if (!rows.find((r) => r[value_fieldname] === type)) {
			const row = frappe.model.add_child(frm.doc, child_doctype, table_fieldname);
			row[value_fieldname] = type;
		}
	});
}
