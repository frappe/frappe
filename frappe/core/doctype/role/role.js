// Copyright (c) 2022, Frappe Technologies Pvt. Ltd. and Contributors
// MIT License. See LICENSE

// Permission-flag metadata + the add/edit dialog live in the shared permission editor
// (frappe.ui.PermissionDialog / frappe.perm_editor), so the Role form and the DocType
// Settings permissions tab share one implementation.
const { PERM_FLAGS, ALL_PERM_FLAGS, capitalize } = frappe.perm_editor;

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
			add_button: { label: __("Add User"), action: () => this.add() },
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
			page_size: 50,
			description: __("DocTypes this role can access."),
			empty_message: __("No DocTypes are accessible to this role."),
			add_button: { label: __("Add Permission"), action: () => this.add() },
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
		new frappe.ui.PermissionDialog(this, { row }).show();
	}

	add() {
		new frappe.ui.PermissionDialog(this, {}).show();
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

		// Standard row: one sequential call triggers setup_custom_perms (converts
		// standard DocPerm → Custom DocPerm), then set_value on the new row.
		// Deliberately use "read" (not "if_owner") as the trigger flag so that
		// if_owner is not mutated before we look up the row by it.
		return frappe
			.call({
				method: "frappe.core.page.permission_manager.permission_manager.update",
				args: {
					doctype: row.parent,
					role: this.role,
					permlevel: row.permlevel,
					ptype: "read",
					value: data.read,
					if_owner: row.if_owner || 0,
				},
			})
			.then(() =>
				frappe.db.get_value(
					"Custom DocPerm",
					{
						parent: row.parent,
						role: this.role,
						permlevel: row.permlevel,
						if_owner: row.if_owner || 0,
					},
					"name"
				)
			)
			.then((r) => {
				const name = r.message && r.message.name;
				if (!name)
					frappe.throw(__("Permission row not found after conversion. Please refresh."));
				return frappe.db.set_value("Custom DocPerm", name, data);
			});
	}

	remove(row) {
		return frappe.call({
			method: "frappe.core.page.permission_manager.permission_manager.remove",
			args: {
				doctype: row.parent,
				role: this.role,
				permlevel: row.permlevel,
				if_owner: row.if_owner || 0,
			},
		});
	}

	perm_data(values) {
		const data = {};
		["if_owner", ...ALL_PERM_FLAGS].forEach((flag) => (data[flag] = values[flag] ? 1 : 0));
		return data;
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
			add_button: { label: __("Add Report"), action: () => this.add() },
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
			add_button: { label: __("Add Page"), action: () => this.add() },
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
			add_button: { label: __("Add Workspace"), action: () => this.add() },
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

function placeholder_html(message) {
	return `<div class="text-muted">${message}</div>`;
}
