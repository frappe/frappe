// Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and Contributors
// MIT License. See LICENSE

// Shared permission editor: the add/edit role-permission dialog and its constants.
// Used by the Role form (role-centric: fixed role, doctype varies) and the DocType
// Settings permissions tab (doctype-centric: fixed doctype, role varies). The host
// supplies a `tab` with `role`, `update(row, values)`, `create(values)`, `remove(row)`
// and `refresh()`, so this file owns only the UI + the perm-flag metadata.

frappe.provide("frappe.perm_editor");

// Full permission set for the dialog, grouped into sections with help text.
const PERM_SECTIONS = [
	{
		label: __("Primary"),
		flags: [
			{ name: "read", description: __("Allows the user to view the document.") },
			{
				name: "write",
				description: __("Allows the user to edit existing records they have access to."),
			},
			{ name: "create", description: __("Allows the user to create new documents.") },
			{ name: "delete", description: __("Allows the user to delete documents.") },
			{
				name: "submit",
				description: __("Allows the user to submit documents."),
			},
			{ name: "cancel", description: __("Allows the user to cancel submitted documents.") },
			{
				name: "amend",
				description: __("Allows the user to amend a cancelled document into a new copy."),
			},
			{
				name: "select",
				description: __(
					"Allows the user to search and select records in other forms. This does not allow the user to view the record itself."
				),
			},
			{
				name: "mask",
				description: __(
					"Allows the user to view the value of a masked field in the document."
				),
			},
		],
	},
	{
		label: __("Reporting & Sharing"),
		flags: [
			{
				name: "report",
				description: __("Allows the user to access reports related to the document."),
			},
			{
				name: "export",
				description: __("Allows the user to export document data from the system."),
			},
			{
				name: "import",
				description: __("Allows the user to use import documents into the system."),
			},
			{
				name: "share",
				description: __(
					"Allows the user to share document access with other users who may not have access to the document themselves."
				),
			},
			{
				name: "print",
				description: __("Allows the user to print or download the document as a PDF."),
			},
			{
				name: "email",
				description: __("Allows the user to send emails linked to the document."),
			},
		],
	},
];

// Flags shown as columns in compact permission tables.
const PERM_FLAGS = ["read", "write", "create", "delete", "submit", "cancel", "amend"];
// Every flag the dialog can write back.
const ALL_PERM_FLAGS = PERM_SECTIONS.flatMap((section) => section.flags.map((flag) => flag.name));
// Permission levels offered in the add dialog (0–9).
const PERMLEVEL_OPTIONS = Array.from({ length: 10 }, (_, i) => String(i)).join("\n");
// Rights that only apply to submittable doctypes (hidden otherwise).
const SUBMITTABLE_FLAGS = ["submit", "cancel", "amend"];
// At permlevel > 0, only these field-level rights apply.
const PERMLEVEL_FLAGS = ["read", "write", "mask"];

function section_break_fieldname(label) {
	return (
		"sb_" +
		label
			.toLowerCase()
			.replace(/[^a-z0-9]+/g, "_")
			.replace(/_+$/, "")
	);
}

function capitalize(string) {
	return string.charAt(0).toUpperCase() + string.slice(1);
}

// Expose the metadata/helpers so hosts can build matching columns / perm payloads.
Object.assign(frappe.perm_editor, {
	PERM_FLAGS,
	PERM_SECTIONS,
	ALL_PERM_FLAGS,
	PERMLEVEL_OPTIONS,
	SUBMITTABLE_FLAGS,
	PERMLEVEL_FLAGS,
	section_break_fieldname,
	capitalize,
});

frappe.ui.PermissionDialog = class PermissionDialog {
	constructor(tab, opts) {
		this.tab = tab;
		this.row = opts.row || null;
		this.is_submittable = this.row ? !!this.row.is_submittable : false;
	}

	get role() {
		return this.tab.role;
	}

	get is_edit() {
		return !!this.row;
	}

	// Add mode where the adapter fixes the doctype and varies the role (the DocType Settings
	// permissions tab). Role-centric add (role.js) leaves `tab.doctype` unset.
	get is_doctype_centric() {
		return !this.is_edit && !this.tab.role && !!this.tab.doctype;
	}

	show() {
		this.dialog = new frappe.ui.Dialog({
			title: this.title(),
			fields: this.fields(),
			primary_action_label: this.is_edit ? __("Save") : __("Add"),
			primary_action: (values) => this.save(values),
		});
		if (this.is_edit) this.add_row_actions();
		this.dialog.show();
		this.apply_visibility(this.is_edit ? this.row.permlevel : 0);
		// Doctype-centric add has a fixed doctype, so resolve its submittable flag up front
		// (role-centric add does this on doctype change instead).
		if (this.is_doctype_centric) {
			frappe.db.get_value("DocType", this.tab.doctype, "is_submittable").then((r) => {
				this.is_submittable = !!(r.message && cint(r.message.is_submittable));
				this.refresh_visibility();
			});
		}
	}

	title() {
		if (this.is_edit)
			return __("{0} Permission for {1}", [__(this.row.source), this.row.parent]);
		return __("Add Permission for {0}", [
			this.is_doctype_centric ? this.tab.doctype : this.role,
		]);
	}

	fields() {
		const level_field = this.is_edit ? this.edit_level_field() : this.add_level_field();
		const seed = this.is_edit ? this.row : { read: 1 };
		return [
			...this.subject_fields(),
			level_field,
			...this.flag_fields(seed),

			{
				fieldtype: "Section Break",
				fieldname: "sb_only_if_creator",
				label: __("Creator's Access"),
			},

			this.if_owner_field(seed),
		];
	}

	// The "subject" of the permission. Doctype-centric add picks the role (doctype fixed);
	// role-centric add and edit keep the doctype field.
	subject_fields() {
		if (this.is_doctype_centric) {
			return [
				{
					fieldtype: "Link",
					fieldname: "role",
					label: __("Role"),
					options: "Role",
					reqd: 1,
					get_query: () => ({ filters: { disabled: 0 } }),
				},
				{
					fieldtype: "Link",
					fieldname: "ref_doctype",
					label: __("DocType"),
					options: "DocType",
					read_only: 1,
					default: this.tab.doctype,
				},
			];
		}
		return [this.doctype_field()];
	}

	doctype_field() {
		if (this.is_edit) {
			return {
				fieldtype: "Link",
				fieldname: "ref_doctype",
				label: __("DocType"),
				options: "DocType",
				read_only: 1,
				default: this.row.parent,
			};
		}
		return {
			fieldtype: "Link",
			fieldname: "ref_doctype",
			label: __("DocType"),
			options: "DocType",
			reqd: 1,
			onchange: () => this.on_doctype_change(),
		};
	}

	edit_level_field() {
		const level = String(this.row.permlevel || 0);
		return {
			fieldtype: "Select",
			fieldname: "permlevel",
			label: __("Permission Level"),
			options: level,
			default: level,
			read_only: 1,
		};
	}

	add_level_field() {
		return {
			fieldtype: "Select",
			fieldname: "permlevel",
			label: __("Permission Level"),
			options: PERMLEVEL_OPTIONS,
			default: "0",
			onchange: () => this.refresh_visibility(),
		};
	}

	flag_fields(seed) {
		const fields = [];
		PERM_SECTIONS.forEach((section) => {
			fields.push({
				fieldtype: "Section Break",
				fieldname: section_break_fieldname(section.label),
				label: __(section.label),
			});
			const half = Math.ceil(section.flags.length / 2);
			section.flags.forEach((flag, i) => {
				if (i === half) fields.push({ fieldtype: "Column Break" });
				fields.push(this.check_field(flag.name, flag.description, seed));
			});
		});
		return fields;
	}

	check_field(fieldname, description, seed) {
		return {
			fieldtype: "Check",
			fieldname,
			label: __(capitalize(fieldname)),
			description: __(description),
			show_description_on_click: 1,
			default: seed[fieldname] || 0,
		};
	}

	if_owner_field(seed) {
		const field = this.check_field(
			"if_owner",
			"When checked, these permissions apply only to documents this user created.",
			seed
		);
		field.label = __("Only if Creator");
		field.show_description_on_click = 0;
		return field;
	}

	on_doctype_change() {
		const doctype = this.dialog.get_value("ref_doctype");
		if (!doctype) {
			this.is_submittable = false;
			return this.refresh_visibility();
		}
		// The submittable flag decides whether submit/cancel/amend apply.
		frappe.db.get_value("DocType", doctype, "is_submittable").then((r) => {
			this.is_submittable = !!(r.message && cint(r.message.is_submittable));
			this.refresh_visibility();
		});
	}

	refresh_visibility() {
		this.apply_visibility(this.dialog.get_value("permlevel"));
	}

	apply_visibility(permlevel) {
		const high_level = cint(permlevel) > 0;
		const visible = (flag) => {
			if (!this.is_submittable && SUBMITTABLE_FLAGS.includes(flag)) return false;
			if (high_level && !PERMLEVEL_FLAGS.includes(flag)) return false;
			return true;
		};
		ALL_PERM_FLAGS.forEach((flag) =>
			this.dialog.set_df_property(flag, "hidden", visible(flag) ? 0 : 1)
		);
		this.dialog.set_df_property("sb_only_if_creator", "hidden", high_level ? 1 : 0);
		this.dialog.set_df_property("if_owner", "hidden", high_level ? 1 : 0);
		PERM_SECTIONS.forEach((section) => {
			const any = section.flags.some((flag) => visible(flag.name));
			this.dialog.set_df_property(
				section_break_fieldname(section.label),
				"hidden",
				any ? 0 : 1
			);
		});
	}

	add_row_actions() {
		this.dialog.add_custom_action(__("Remove Permission"), () => this.confirm_remove());
	}

	save(values) {
		const promise = this.is_edit ? this.tab.update(this.row, values) : this.tab.create(values);
		promise
			.then(() => {
				this.dialog.hide();
				frappe.show_alert({
					message: this.is_edit ? __("Permission updated.") : __("Permission added."),
					indicator: "green",
				});
				this.tab.refresh();
			})
			.catch((e) => {
				frappe.msgprint({
					title: __("Error"),
					message: e.message || __("Failed to save permission."),
					indicator: "red",
				});
			});
	}

	confirm_remove() {
		frappe.confirm(__("Remove this role's permission on {0}?", [this.row.parent]), () => {
			this.tab
				.remove(this.row)
				.then(() => {
					this.dialog.hide();
					frappe.show_alert({ message: __("Permission removed."), indicator: "green" });
					this.tab.refresh();
				})
				.catch((e) => {
					frappe.msgprint({
						title: __("Error"),
						message: e.message || __("Failed to remove permission."),
						indicator: "red",
					});
				});
		});
	}
};
