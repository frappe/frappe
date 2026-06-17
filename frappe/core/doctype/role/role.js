// Copyright (c) 2022, Frappe Technologies Pvt. Ltd. and Contributors
// MIT License. See LICENSE

// Flags shown as columns in the Documents table (compact view).
const PERM_FLAGS = ["read", "write", "create", "delete", "submit", "cancel", "amend"];

// Full permission set for the add/edit dialog, grouped into three sections with
// help text. Strings are translated lazily at field-build time, not at load.
const PERM_SECTIONS = [
	{
		label: "Primary",
		flags: [
			{ name: "read", description: "View documents of this type." },
			{ name: "write", description: "Edit existing documents." },
			{ name: "create", description: "Create new documents." },
			{ name: "delete", description: "Delete documents." },
			{ name: "submit", description: "Submit documents (submittable doctypes)." },
			{ name: "cancel", description: "Cancel submitted documents." },
			{ name: "amend", description: "Amend a cancelled document into a new copy." },
			{ name: "select", description: "Select records in link fields." },
		],
	},
	{
		label: "Reporting & Sharing",
		flags: [
			{ name: "report", description: "Run reports for this DocType." },
			{ name: "export", description: "Export records to a file." },
			{ name: "import", description: "Import records from a file." },
			{ name: "share", description: "Share documents with specific users." },
			{ name: "print", description: "Print documents." },
			{ name: "email", description: "Email documents." },
		],
	},
	{
		label: "Others",
		flags: [{ name: "mask", description: "Mask sensitive field values." }],
	},
];

// Every flag the dialog can write back (across all three sections).
const ALL_PERM_FLAGS = PERM_SECTIONS.flatMap((section) => section.flags.map((flag) => flag.name));

// Permission levels offered in the add dialog (0–9).
const PERMLEVEL_OPTIONS = Array.from({ length: 10 }, (_, i) => String(i)).join("\n");

// Rights that only apply to submittable doctypes (hidden otherwise).
const SUBMITTABLE_FLAGS = ["submit", "cancel", "amend"];
// At permlevel > 0, only these field-level rights apply.
const PERMLEVEL_FLAGS = ["read", "write", "mask"];

frappe.ui.form.on("Role", {
	refresh(frm) {
		frm.role_form = new RoleForm(frm);
		frm.role_form.render();
	},

	on_tab_change(frm) {
		frm.role_form && frm.role_form.load_active_tab();
	},
});

// ============================================================
// RoleForm — top-level controller for the form.
// ============================================================

class RoleForm {
	constructor(frm) {
		this.frm = frm;
	}

	get role() {
		return this.frm.doc.name;
	}

	render() {
		this.show_banner();
		this.frm.set_df_property(
			"is_custom",
			"read_only",
			frappe.session.user !== "Administrator"
		);
		this.add_buttons();
		this.setup_tabs();
	}

	setup_tabs() {
		// Keyed by Tab Break fieldname so `load_active_tab` can find the editor.
		this.tabs = {
			users_tab: new UsersTab(this.frm),
			document_tab: new DocumentsTab(this.frm),
			report_tab: new ReportsTab(this.frm),
			pages_tab: new PagesTab(this.frm),
			workspace_tab: new WorkspacesTab(this.frm),
		};
		Object.values(this.tabs).forEach((tab) => tab.build());

		// Role Profiles live in the always-visible Details tab — load eagerly.
		const profiles = new RoleProfilesTab(this.frm);
		profiles.build();
		profiles.refresh();

		this.load_active_tab();
	}

	load_active_tab() {
		// Refresh on every activation so externally-made changes show up without a
		// full form reload (the first activation is also when the tab lazy-loads).
		const active = this.frm.get_active_tab && this.frm.get_active_tab();
		const fieldname = active && active.df && active.df.fieldname;
		const tab = fieldname && this.tabs && this.tabs[fieldname];
		if (tab) tab.refresh();
	}

	show_banner() {
		const messages = {
			All: __("Role 'All' will be given to all system + website users."),
			"Desk User": __("Role 'Desk User' will be given to all system users."),
		};
		if (messages[this.role]) this.frm.dashboard.add_comment(messages[this.role], "yellow");
	}

	add_buttons() {
		this.frm.add_custom_button(
			__("Role Permissions Manager"),
			() => {
				frappe.route_options = { role: this.role };
				frappe.set_route("permission-manager");
			},
			__("View")
		);
		if (frappe.user.has_role("System Manager")) {
			this.frm.add_custom_button(
				__("Replicate Role"),
				() => new ReplicateRoleDialog(this.frm).show(),
				__("Action")
			);
		}
	}
}

// ============================================================
// RoleTab — base class for a tab backed by an EmbeddedList.
// ============================================================

class RoleTab {
	constructor(frm, html_fieldname) {
		this.frm = frm;
		this.html_fieldname = html_fieldname;
	}

	get role() {
		return this.frm.doc.name;
	}

	get wrapper() {
		const field = this.frm.fields_dict[this.html_fieldname];
		return field ? field.$wrapper : null;
	}

	// Builds the EmbeddedList, or a placeholder for an unsaved role.
	build() {
		const wrapper = this.wrapper && this.wrapper.empty();
		if (!wrapper) return;
		if (this.frm.is_new()) {
			wrapper.html(placeholder_html(__("Save the role first to view this information.")));
			return;
		}
		this.list = new frappe.ui.EmbeddedList(
			Object.assign({ wrapper, show_index: true }, this.list_config())
		);
	}

	refresh() {
		this.list && this.list.refresh();
	}

	// Subclasses return the EmbeddedList options (minus wrapper/show_index).
	list_config() {
		return {};
	}
	save_roles_on_doc(doctype, name, transform) {
		return frappe.db.get_doc(doctype, name).then((doc) => {
			doc.roles = transform(doc.roles || []);
			return client_save(doc);
		});
	}
}

// ============================================================
// RoleProfilesTab (Details tab) & UsersTab
// ============================================================

class RoleProfilesTab extends RoleTab {
	constructor(frm) {
		super(frm, "role_profiles_html");
	}

	list_config() {
		return {
			description: __("Role Profiles that include this role."),
			empty_message: __("No Role Profiles include this role."),
			columns: [
				{
					label: __("Role Profile"),
					fieldname: "name",
					type: "link",
					route: (row) => ["Form", "Role Profile", row.name],
				},
			],
			get_data: () => this.get_data(),
		};
	}

	get_data() {
		return frappe.db
			.get_list("Has Role", {
				filters: { role: this.role, parenttype: "Role Profile" },
				fields: ["parent"],
				limit: 0,
			})
			.then((rows) => unique_parents(rows).map((parent) => ({ name: parent })));
	}
}

class UsersTab extends RoleTab {
	constructor(frm) {
		super(frm, "users_html");
	}

	list_config() {
		return {
			description: __("Users who have this role."),
			empty_message: __("No users have this role."),
			add_button: { label: __("+ Add User"), action: () => this.add() },
			columns: [
				{
					label: __("Full Name"),
					fieldname: "full_name",
					type: "link",
					text: (row) => row.full_name || row.name,
					route: (row) => ["Form", "User", row.name],
				},
				{ label: __("Email"), fieldname: "email" },
				{
					type: "actions",
					actions: [
						{
							label: __("Remove"),
							icon: "x",
							danger: true,
							confirm: __("Remove {0} from this role?"),
							confirm_field: "full_name",
							action: (row, refresh) => this.remove(row.name).then(refresh),
						},
					],
				},
			],
			get_data: () => this.get_data(),
		};
	}

	get_data() {
		return frappe.db
			.get_list("Has Role", {
				filters: { role: this.role, parenttype: "User" },
				fields: ["parent"],
				limit: 0,
			})
			.then((rows) => this.fetch_users(unique_parents(rows)));
	}

	fetch_users(names) {
		if (!names.length) return [];
		return frappe.db.get_list("User", {
			filters: { name: ["in", names], enabled: 1 },
			fields: ["name", "full_name", "email"],
			order_by: "full_name asc",
			limit: 0,
		});
	}

	add() {
		const existing = unique_values(this.list.data, "name");
		const dialog = new frappe.ui.Dialog({
			title: __("Add User to {0}", [this.role]),
			fields: [
				{
					label: __("User"),
					fieldname: "user",
					fieldtype: "Link",
					options: "User",
					reqd: 1,
					get_query: () => ({
						filters: { enabled: 1, name: ["not in", not_in(existing)] },
					}),
				},
			],
			primary_action_label: __("Add"),
			primary_action: (values) => {
				this.add_role(values.user)
					.then(() => {
						dialog.hide();
						frappe.show_alert({ message: __("User added."), indicator: "green" });
						this.refresh();
					})
					.catch((e) => {
						frappe.show_alert({
							message: e.message || __("Failed to add user."),
							indicator: "red",
						});
					});
			},
		});
		dialog.show();
	}

	add_role(user_name) {
		return this.save_roles_on_doc("User", user_name, (roles) => {
			if (!roles.find((r) => r.role === this.role)) roles.push({ role: this.role });
			return roles;
		});
	}

	remove(user_name) {
		return this.save_roles_on_doc("User", user_name, (roles) =>
			roles.filter((r) => r.role !== this.role)
		);
	}
}

// ============================================================
// DocumentsTab — DocPerm + Custom DocPerm via get_permissions.
// ============================================================

class DocumentsTab extends RoleTab {
	constructor(frm) {
		super(frm, "document_permissions_html");
	}

	list_config() {
		return {
			page_size: 20,
			description: __("DocTypes this role can access."),
			empty_message: __("No DocTypes are accessible to this role."),
			add_button: { label: __("+ Add Permission"), action: () => this.add() },
			columns: this.columns(),
			on_row_click: (row) => this.edit(row),
			get_data: () => this.get_data(),
		};
	}

	get_data() {
		return frappe
			.call({
				method: "frappe.core.page.permission_manager.permission_manager.get_permissions",
				args: { role: this.role },
			})
			.then((r) => this.transform(r.message || []));
	}

	transform(perms) {
		return perms
			.map((perm) => ({ ...perm, source: perm.parenttype ? "Standard" : "Custom" }))
			.sort(
				(a, b) =>
					a.parent.localeCompare(b.parent) || (a.permlevel || 0) - (b.permlevel || 0)
			);
	}

	columns() {
		const cols = [
			{ label: __("DocType"), fieldname: "parent" },
			{
				label: __("Type"),
				fieldname: "source",
				type: "badge",
				color: (row) => (row.source === "Custom" ? "blue" : "gray"),
			},
			{ label: __("Permission Level"), fieldname: "permlevel", align: "center" },
			{
				label: __("Only if Creator"),
				fieldname: "if_owner",
				type: "check",
				align: "center",
			},
		];
		PERM_FLAGS.forEach((flag) =>
			cols.push({
				label: __(capitalize(flag)),
				fieldname: flag,
				type: "check",
				align: "center",
			})
		);
		return cols;
	}

	edit(row) {
		new PermissionDialog(this, { row }).show();
	}

	add() {
		new PermissionDialog(this, {}).show();
	}

	create(values) {
		const doctype = values.ref_doctype;
		const permlevel = cint(values.permlevel);
		return frappe
			.call({
				method: "frappe.core.page.permission_manager.permission_manager.add",
				args: { parent: doctype, role: this.role, permlevel },
			})
			.then(() =>
				frappe.db.get_list("Custom DocPerm", {
					filters: { parent: doctype, role: this.role, permlevel, if_owner: 0 },
					fields: ["name"],
					order_by: "creation desc",
					limit: 1,
				})
			)
			.then((rows) => {
				const name = rows && rows[0] && rows[0].name;
				return name
					? frappe.db.set_value("Custom DocPerm", name, this.perm_data(values))
					: null;
			});
	}

	update(row, values) {
		const data = this.perm_data(values);
		if (row.source === "Custom") {
			return frappe.db.set_value("Custom DocPerm", row.name, data);
		}
		return frappe.db.get_doc("DocType", row.parent).then((dt) => {
			const perm = (dt.permissions || []).find((p) => p.name === row.name);
			if (!perm) {
				frappe.throw(
					__("Permission row not found. It may have been removed — please refresh.")
				);
			}
			Object.assign(perm, data);
			return client_save(dt);
		});
	}

	remove(row) {
		if (row.source === "Custom") {
			return frappe.db.delete_doc("Custom DocPerm", row.name);
		}
		return frappe.db.get_doc("DocType", row.parent).then((dt) => {
			dt.permissions = (dt.permissions || []).filter((p) => p.name !== row.name);
			return client_save(dt);
		});
	}

	perm_data(values) {
		const data = {};
		["if_owner", ...ALL_PERM_FLAGS].forEach((flag) => (data[flag] = values[flag] ? 1 : 0));
		return data;
	}
}

// ============================================================
// PermissionDialog — the add / edit permission dialog.
// ============================================================

class PermissionDialog {
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
	}

	title() {
		return this.is_edit
			? __("{0} Permission for {1}", [__(this.row.source), this.row.parent])
			: __("Add Permission for {0}", [this.role]);
	}

	fields() {
		const level_field = this.is_edit ? this.edit_level_field() : this.add_level_field();
		const seed = this.is_edit ? this.row : { read: 1 };
		return [
			this.doctype_field(),
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
			"Apply this permission only to documents created by the user.",
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
}

// ============================================================
// ============================================================
// ReportsTab & PagesTab — direct lookup on the `roles` child table.
// ============================================================

class RoleAccessTab extends RoleTab {
	get_data() {
		return frappe.db
			.get_list("Has Role", {
				filters: { role: this.role, parenttype: this.access_doctype },
				fields: ["parent"],
				limit: 0,
			})
			.then((rows) => {
				const names = unique_parents(rows);
				return this.fetch_records(names);
			});
	}

	fetch_records(names) {
		if (!names.length) return [];
		return frappe.db.get_list(this.access_doctype, {
			filters: { name: ["in", names] },
			fields: this.meta_fields,
			order_by: "name asc",
			limit: 0,
		});
	}

	name_link_column() {
		return {
			label: __(this.label),
			fieldname: "name",
			type: "link",
			route: (row) => ["Form", this.access_doctype, row.name],
		};
	}

	remove_action_column() {
		return {
			type: "actions",
			actions: [
				{
					label: __("Remove"),
					icon: "x",
					danger: true,
					confirm: __("Remove this role's access to {0}?"),
					confirm_field: "name",
					action: (row, refresh) => this.remove(row.name).then(refresh),
				},
			],
		};
	}

	add() {
		const existing = unique_values(this.list.data, "name");
		const dialog = new frappe.ui.Dialog({
			title: __("Add {0} Access to {1}", [__(this.label), this.role]),
			fields: [
				{
					label: __(this.label),
					fieldname: "doc",
					fieldtype: "Link",
					options: this.access_doctype,
					reqd: 1,
					get_query: () => ({ filters: { name: ["not in", not_in(existing)] } }),
				},
			],
			primary_action_label: __("Add"),
			primary_action: (values) => {
				this.add_role(values.doc)
					.then(() => {
						dialog.hide();
						frappe.show_alert({ message: __("Access added."), indicator: "green" });
						this.refresh();
					})
					.catch((e) => {
						frappe.show_alert({
							message: e.message || __("Failed to add access."),
							indicator: "red",
						});
					});
			},
		});
		dialog.show();
	}

	add_role(record_name) {
		return this.save_roles_on_doc(this.access_doctype, record_name, (roles) => {
			if (!roles.find((r) => r.role === this.role)) roles.push({ role: this.role });
			return roles;
		});
	}

	remove(record_name) {
		return this.save_roles_on_doc(this.access_doctype, record_name, (roles) =>
			roles.filter((r) => r.role !== this.role)
		);
	}
}

class ReportsTab extends RoleAccessTab {
	constructor(frm) {
		super(frm, "report_roles_html");
		this.access_doctype = "Report";
		this.label = "Report";
		this.meta_fields = ["name", "module", "report_type", "ref_doctype"];
	}

	report_route(row) {
		if (row.report_type === "Report Builder") {
			return ["List", row.ref_doctype, "Report", row.name];
		}
		return ["query-report", row.name];
	}

	list_config() {
		return {
			description: __("Reports this role can access."),
			empty_message: __("This role has no Report access."),
			add_button: { label: __("+ Add Report"), action: () => this.add() },
			columns: [
				{
					label: __("Report"),
					fieldname: "name",
					type: "link",
					route: (row) => this.report_route(row),
				},
				{ label: __("Module"), fieldname: "module" },
				this.remove_action_column(),
			],
			get_data: () => this.get_data(),
		};
	}
}

class PagesTab extends RoleAccessTab {
	constructor(frm) {
		super(frm, "page_roles_html");
		this.access_doctype = "Page";
		this.label = "Page";
		this.meta_fields = ["name", "title", "module"];
	}

	list_config() {
		return {
			description: __("Pages this role can access."),
			empty_message: __("This role has no Page access."),
			add_button: { label: __("+ Add Page"), action: () => this.add() },
			columns: [
				{
					label: __("Title"),
					fieldname: "title",
					type: "link",
					text: (row) => row.title || row.name,
					route: (row) => ["Form", "Page", row.name],
				},
				{ label: __("Module"), fieldname: "module" },
				this.remove_action_column(),
			],
			get_data: () => this.get_data(),
		};
	}
}

class WorkspacesTab extends RoleAccessTab {
	constructor(frm) {
		super(frm, "workspace_roles_html");
		this.access_doctype = "Workspace";
		this.label = "Workspace";
		this.meta_fields = ["name", "title", "module"];
	}

	list_config() {
		return {
			description: __("Workspaces this role can access."),
			empty_message: __("This role has no Workspace access."),
			add_button: { label: __("+ Add Workspace"), action: () => this.add() },
			columns: [
				{
					label: __("Workspace"),
					fieldname: "title",
					type: "link",
					text: (row) => row.title || row.name,
					route: (row) => [row.name],
				},
				{ label: __("Module"), fieldname: "module" },
				this.remove_action_column(),
			],
			get_data: () => this.get_data(),
		};
	}
}

// ============================================================
// ReplicateRoleDialog
// ============================================================

class ReplicateRoleDialog {
	constructor(frm) {
		this.frm = frm;
	}

	show() {
		this.dialog = new frappe.ui.Dialog({
			title: __("Replicate Role"),
			fields: [
				{
					label: __("New Role Name"),
					fieldname: "new_role_name",
					fieldtype: "Data",
					default: this.frm.doc.name,
					reqd: 1,
				},
			],
			freeze: true,
			freeze_message: __("Replicating Role..."),
			primary_action_label: __("Replicate"),
			primary_action: (values) => this.replicate(values.new_role_name),
		});
		this.dialog.show();
	}

	replicate(new_role) {
		this.dialog.hide();
		frappe.call({
			method: "replicate_role",
			doc: this.frm.doc,
			args: { cur_role: this.frm.doc.name, new_role },
			callback: (r) => this.on_replicated(r),
		});
	}

	on_replicated(r) {
		if (r.message) {
			frappe.set_route("Form", "Role", r.message);
			frappe.show_alert({
				message: __("New role created successfully."),
				indicator: "green",
			});
		} else if (r.exc) {
			JSON.parse(r.exc).forEach((err) =>
				frappe.show_alert({ message: __(err), indicator: "red" })
			);
		}
	}
}

// ============================================================
// Helpers
// ============================================================

function client_save(doc) {
	return frappe.call({ method: "frappe.client.save", args: { doc } });
}

function unique_parents(rows) {
	return [...new Set(rows.map((row) => row.parent))];
}

// Distinct, defined values of `field` across rows (used to exclude already-listed
// records from the Add dialogs).
function unique_values(rows, field) {
	return [...new Set((rows || []).map((row) => row[field]).filter(Boolean))];
}

// A safe "not in" list for link filters (empty lists confuse the query builder).
function not_in(values) {
	return values.length ? values : [""];
}

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

function placeholder_html(message) {
	return `<div class="text-muted">${message}</div>`;
}
