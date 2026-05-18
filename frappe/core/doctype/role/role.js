// Copyright (c) 2022, Frappe Technologies Pvt. Ltd. and Contributors
// MIT License. See LICENSE

const PERM_FLAGS = ["read", "write", "create", "delete", "submit", "cancel", "amend"];
const SOURCE_STANDARD = "Standard";
const SOURCE_CUSTOM = "Custom";

frappe.ui.form.on("Role", {
	refresh: function (frm) {
		show_role_banner(frm);
		frm.set_df_property("is_custom", "read_only", frappe.session.user !== "Administrator");
		add_role_buttons(frm);
		new UserEditor(frm).render();
		new PermissionEditor(frm).render();
	},
});

// ============================================================
// UserEditor
// ============================================================

class UserEditor {
	constructor(frm) {
		this.frm = frm;
		this.fieldname = "users_html";
		this.users = [];
	}

	get wrapper() {
		const field = this.frm.fields_dict[this.fieldname];
		return field ? field.$wrapper : null;
	}

	get role() {
		return this.frm.doc.name;
	}

	render() {
		const wrapper = this.wrapper;
		if (!wrapper) return;

		if (this.frm.is_new()) {
			render_empty(wrapper, __("Save the role to view users."));
			return;
		}

		this.refresh();
	}

	refresh() {
		this.fetch_users().then((users) => {
			this.users = users;
			const body = users.length
				? this.build_table_html(users)
				: `<div class="text-muted">${__("No users have this role.")}</div>`;

			this.wrapper.html(this.build_add_button_html() + body);
			this.bind_add_button();
			this.bind_remove_button();
			this.bind_row_click();
		});
	}

	// --- Fetching ---

	fetch_users() {
		return frappe.db
			.get_list("Has Role", {
				filters: { role: this.role, parenttype: "User" },
				fields: ["parent"],
				limit: 0,
			})
			.then((rows) => {
				const user_names = rows.map((r) => r.parent);
				if (!user_names.length) return [];
				return frappe.db.get_list("User", {
					filters: { name: ["in", user_names], enabled: 1 },
					fields: ["name", "full_name", "email"],
					order_by: "full_name asc",
					limit: 0,
				});
			});
	}

	// --- HTML building ---

	build_table_html(users) {
		const headers = [__("Full Name"), __("Email"), ""];
		const rows = users.map((u) => this.build_row(u));
		return build_table_html(headers, rows);
	}

	build_row(user) {
		const name = frappe.utils.escape_html(user.name);
		const full_name = frappe.utils.escape_html(user.full_name || "");
		const email = frappe.utils.escape_html(user.email || "");
		return `<tr style="cursor: pointer;" data-user="${name}">
			<td>${full_name}</td>
			<td>${email}</td>
			<td class="text-center" style="width: 40px;">
				<button class="btn btn-xs btn-link text-danger" data-action="remove-user" title="${__(
					"Remove from role"
				)}">
					${frappe.utils.icon("x", "sm")}
				</button>
			</td>
		</tr>`;
	}

	build_add_button_html() {
		return `<div class="mb-3">
			<button class="btn btn-default" data-action="add-user">
				${__("+ Add User")}
			</button>
		</div>`;
	}

	// --- Event bindings ---

	bind_add_button() {
		this.wrapper.find("[data-action='add-user']").on("click", () => this.show_add_dialog());
	}

	bind_remove_button() {
		this.wrapper.find("[data-action='remove-user']").on("click", (e) => {
			e.stopPropagation();
			const user_name = $(e.currentTarget).closest("tr").attr("data-user");
			frappe.confirm(__("Remove '{0}' from role '{1}'?", [user_name, this.role]), () =>
				this.remove_user_from_role(user_name).then(() =>
					this.after_change(__("User removed."))
				)
			);
		});
	}

	bind_row_click() {
		this.wrapper.find("tr[data-user]").on("click", function () {
			frappe.set_route("Form", "User", $(this).attr("data-user"));
		});
	}

	after_change(message) {
		frappe.show_alert({ message, indicator: "green" });
		this.refresh();
	}

	// --- Dialog ---

	show_add_dialog() {
		const existing = this.users.map((u) => u.name);
		const role = this.role;
		const dialog = new frappe.ui.Dialog({
			title: __("Add User to '{0}'", [role]),
			fields: [
				{
					label: __("User"),
					fieldname: "user",
					fieldtype: "Link",
					options: "User",
					reqd: 1,
					get_query: () => ({
						filters: {
							enabled: 1,
							name: ["not in", existing.length ? existing : [""]],
						},
					}),
				},
			],
			primary_action_label: __("Add"),
			primary_action: (values) => {
				this.add_user_to_role(values.user)
					.then(() => {
						dialog.hide();
						this.after_change(__("User added."));
					})
					.catch(() => {});
			},
		});
		dialog.show();
	}

	// --- Mutations (modify the parent User doc) ---

	add_user_to_role(user_name) {
		return frappe.db.get_doc("User", user_name).then((user) => {
			user.roles = user.roles || [];
			if (!user.roles.find((r) => r.role === this.role)) {
				user.roles.push({ role: this.role });
			}
			return frappe.call({ method: "frappe.client.save", args: { doc: user } });
		});
	}

	remove_user_from_role(user_name) {
		return frappe.db.get_doc("User", user_name).then((user) => {
			user.roles = (user.roles || []).filter((r) => r.role !== this.role);
			return frappe.call({ method: "frappe.client.save", args: { doc: user } });
		});
	}
}

// ============================================================
// PermissionEditor
// ============================================================

class PermissionEditor {
	constructor(frm) {
		this.frm = frm;
		this.fieldname = "permissions_html";
	}

	get wrapper() {
		const field = this.frm.fields_dict[this.fieldname];
		return field ? field.$wrapper : null;
	}

	get role() {
		return this.frm.doc.name;
	}

	get developer_mode() {
		return !!frappe.boot.developer_mode;
	}

	render() {
		const wrapper = this.wrapper;
		if (!wrapper) return;

		if (this.frm.is_new()) {
			render_empty(wrapper, __("Save the role to view permissions."));
			return;
		}

		this.refresh();
	}

	refresh() {
		this.fetch_permissions().then((perms) => {
			const body = perms.length
				? this.build_table_html(perms)
				: `<div class="text-muted">${__(
						"No DocTypes are accessible for this role."
				  )}</div>`;

			this.wrapper.html(this.build_add_button_html() + body);
			this.bind_add_button();
			this.bind_edit_button();
			this.bind_remove_button();
		});
	}

	// --- Fetching / merging ---

	fetch_permissions() {
		const fields = ["name", "parent", "permlevel", ...PERM_FLAGS];
		return Promise.all([
			frappe.db.get_list("DocPerm", {
				filters: { role: this.role, parenttype: "DocType" },
				fields,
				limit: 0,
			}),
			frappe.db.get_list("Custom DocPerm", {
				filters: { role: this.role },
				fields,
				limit: 0,
			}),
		]).then(([standard, custom]) => this.merge_permissions(standard, custom));
	}

	merge_permissions(standard, custom) {
		// Custom DocPerm overrides DocPerm: drop standard rows for doctypes that have any custom row.
		const customized = new Set(custom.map((p) => p.parent));
		const standard_rows = standard
			.filter((p) => !customized.has(p.parent))
			.map((p) => ({ ...p, source: SOURCE_STANDARD }));
		const custom_rows = custom.map((p) => ({ ...p, source: SOURCE_CUSTOM }));
		return [...standard_rows, ...custom_rows].sort((a, b) => {
			const by_dt = a.parent.localeCompare(b.parent);
			return by_dt !== 0 ? by_dt : (a.permlevel || 0) - (b.permlevel || 0);
		});
	}

	fetch_perm_row(existing) {
		const doctype = existing.source === SOURCE_CUSTOM ? "Custom DocPerm" : "DocPerm";
		return frappe.db
			.get_value(doctype, existing.name, ["parent", "permlevel", ...PERM_FLAGS])
			.then((r) => ({ ...existing, ...r.message }));
	}

	// --- HTML building ---

	build_table_html(perms) {
		const headers = [
			__("DocType"),
			__("Level"),
			...PERM_FLAGS.map((f) => __(capitalize(f))),
			__("Source"),
			__("Action"),
		];
		const rows = perms.map((p) => this.build_row(p));
		return build_table_html(headers, rows);
	}

	build_row(p) {
		const parent = frappe.utils.escape_html(p.parent);
		const perm_name = frappe.utils.escape_html(p.name);
		const level = p.permlevel || 0;
		const perm_cells = PERM_FLAGS.map((k) => perm_cell(p[k])).join("");
		return `<tr data-doctype="${parent}" data-perm-name="${perm_name}" data-source="${
			p.source
		}" data-permlevel="${level}">
			<td><a href="/app/doctype/${parent}" onclick="event.stopPropagation();">${parent}</a></td>
			<td class="text-center">${level}</td>
			${perm_cells}
			<td>${__(p.source)}</td>
			<td class="text-center">
				<button class="btn btn-xs btn-link" data-action="edit-perm">${__("Edit")}</button>
				<button class="btn btn-xs btn-link text-danger" data-action="remove-perm" title="${__("Remove")}">
					${frappe.utils.icon("x", "sm")}
				</button>
			</td>
		</tr>`;
	}

	build_add_button_html() {
		return `<div class="mb-3">
			<button class="btn btn-default" data-action="add-perm">
				${__("+ Add Permission")}
			</button>
		</div>`;
	}

	// --- Event bindings ---

	bind_add_button() {
		this.wrapper.find("[data-action='add-perm']").on("click", () => {
			this.show_dialog(null);
		});
	}

	bind_edit_button() {
		this.wrapper.find("[data-action='edit-perm']").on("click", (e) => {
			e.stopPropagation();
			const existing = read_perm_from_row($(e.currentTarget).closest("tr"));
			this.fetch_perm_row(existing).then((perm) => this.show_dialog(perm));
		});
	}

	bind_remove_button() {
		this.wrapper.find("[data-action='remove-perm']").on("click", (e) => {
			e.stopPropagation();
			const existing = read_perm_from_row($(e.currentTarget).closest("tr"));
			frappe.confirm(
				__("Remove '{0}' permission (Level {1}) on {2}?", [
					this.role,
					existing.permlevel,
					existing.parent,
				]),
				() =>
					this.remove_permission(existing).then(() =>
						this.after_change(__("Permission removed."))
					)
			);
		});
	}

	after_change(message) {
		frappe.show_alert({ message, indicator: "green" });
		this.refresh();
	}

	// --- Dialog ---

	show_dialog(existing_perm) {
		const is_edit = !!existing_perm;
		const dialog = new frappe.ui.Dialog({
			title: is_edit
				? __("Edit {0} Permission on {1}", [
						__(existing_perm.source),
						existing_perm.parent,
				  ])
				: __("Add Permission for {0}", [this.role]),
			fields: this.build_dialog_fields(existing_perm),
			primary_action_label: is_edit ? __("Save") : __("Add"),
			primary_action: (values) => {
				const promise = is_edit
					? this.update_permission(existing_perm, values)
					: this.create_permission(values, this.developer_mode && !!values.is_standard);
				promise
					.then(() => {
						dialog.hide();
						this.after_change(
							is_edit ? __("Permission updated.") : __("Permission added.")
						);
					})
					.catch(() => {
						// Frappe shows the error dialog itself; keep the dialog open.
					});
			},
		});
		dialog.show();
	}

	build_dialog_fields(existing_perm) {
		const is_edit = !!existing_perm;
		const fields = [
			{
				label: __("DocType"),
				fieldname: "ref_doctype",
				fieldtype: "Link",
				options: "DocType",
				reqd: 1,
				read_only: is_edit ? 1 : 0,
				default: is_edit ? existing_perm.parent : "",
			},
			{
				label: __("Permission Level"),
				fieldname: "permlevel",
				fieldtype: "Int",
				read_only: is_edit ? 1 : 0,
				default: is_edit ? existing_perm.permlevel || 0 : 0,
			},
			{ fieldtype: "Section Break", label: __("Permissions") },
		];

		PERM_FLAGS.forEach((flag, i) => {
			if (i > 0 && i % 4 === 0) fields.push({ fieldtype: "Column Break" });
			fields.push({
				label: __(capitalize(flag)),
				fieldname: flag,
				fieldtype: "Check",
				default: is_edit ? existing_perm[flag] || 0 : flag === "read" ? 1 : 0,
			});
		});

		if (this.developer_mode && !is_edit) {
			fields.push({ fieldtype: "Section Break" });
			fields.push({
				label: __("Add as Standard DocPerm"),
				fieldname: "is_standard",
				fieldtype: "Check",
				default: 0,
				description: __(
					"Standard rows are stored in the DocType's permissions table and exported to the DocType JSON. Otherwise, a Custom DocPerm is created."
				),
			});
		}

		return fields;
	}

	// --- Mutations: dispatchers ---

	create_permission(values, is_standard) {
		const perm_data = perm_data_from_values({ role: this.role, ...values });
		perm_data.permlevel = values.permlevel || 0;
		return is_standard
			? this.insert_standard_docperm(values.ref_doctype, perm_data)
			: this.insert_custom_docperm(values.ref_doctype, perm_data);
	}

	update_permission(existing, values) {
		const perm_data = perm_data_from_values(values);
		return existing.source === SOURCE_CUSTOM
			? this.update_custom_docperm(existing.name, perm_data)
			: this.update_standard_docperm(existing.parent, existing.name, perm_data);
	}

	remove_permission(existing) {
		return existing.source === SOURCE_CUSTOM
			? this.delete_custom_docperm(existing.name)
			: this.delete_standard_docperm(existing.parent, existing.name);
	}

	// --- Mutations: Custom DocPerm ---

	insert_custom_docperm(doctype, perm_data) {
		return frappe.db.insert({
			doctype: "Custom DocPerm",
			parent: doctype,
			parenttype: "DocType",
			parentfield: "permissions",
			...perm_data,
		});
	}

	update_custom_docperm(name, perm_data) {
		return frappe.db.set_value("Custom DocPerm", name, perm_data);
	}

	delete_custom_docperm(name) {
		return frappe.db.delete_doc("Custom DocPerm", name);
	}

	// --- Mutations: Standard DocPerm (modify the parent DocType) ---

	insert_standard_docperm(doctype, perm_data) {
		return frappe.db.get_doc("DocType", doctype).then((dt) => {
			dt.permissions.push(perm_data);
			return frappe.call({ method: "frappe.client.save", args: { doc: dt } });
		});
	}

	update_standard_docperm(doctype, row_name, perm_data) {
		return frappe.db.get_doc("DocType", doctype).then((dt) => {
			const row = (dt.permissions || []).find((p) => p.name === row_name);
			if (row) Object.assign(row, perm_data);
			return frappe.call({ method: "frappe.client.save", args: { doc: dt } });
		});
	}

	delete_standard_docperm(doctype, row_name) {
		return frappe.db.get_doc("DocType", doctype).then((dt) => {
			dt.permissions = (dt.permissions || []).filter((p) => p.name !== row_name);
			return frappe.call({ method: "frappe.client.save", args: { doc: dt } });
		});
	}
}

// ============================================================
// Module-level helpers
// ============================================================

function render_empty(wrapper, message) {
	wrapper.html(`<div class="text-muted">${message}</div>`);
}

function render_table(wrapper, headers, rows) {
	wrapper.html(build_table_html(headers, rows));
}

function build_table_html(headers, rows) {
	const thead = headers.map((h) => `<th>${h}</th>`).join("");
	return `
		<table class="table table-bordered table-hover">
			<thead><tr>${thead}</tr></thead>
			<tbody>${rows.join("")}</tbody>
		</table>
	`;
}

function perm_cell(value) {
	return `<td class="text-center">${value ? "✓" : ""}</td>`;
}

function read_perm_from_row($row) {
	return {
		name: $row.attr("data-perm-name"),
		parent: $row.attr("data-doctype"),
		permlevel: parseInt($row.attr("data-permlevel"), 10) || 0,
		source: $row.attr("data-source"),
	};
}

function perm_data_from_values(values) {
	const out = {};
	for (const flag of PERM_FLAGS) {
		out[flag] = values[flag] ? 1 : 0;
	}
	if (values.role !== undefined) out.role = values.role;
	return out;
}

function capitalize(s) {
	return s.charAt(0).toUpperCase() + s.slice(1);
}

// ============================================================
// Form chrome
// ============================================================

function show_role_banner(frm) {
	if (frm.doc.name === "All") {
		frm.dashboard.add_comment(
			__("Role 'All' will be given to all system + website users."),
			"yellow"
		);
	} else if (frm.doc.name === "Desk User") {
		frm.dashboard.add_comment(
			__("Role 'Desk User' will be given to all system users."),
			"yellow"
		);
	}
}

function add_role_buttons(frm) {
	frm.add_custom_button(
		__("Role Permissions Manager"),
		() => {
			frappe.route_options = { role: frm.doc.name };
			frappe.set_route("permission-manager");
		},
		__("View")
	);

	frm.add_custom_button(
		__("Show Users"),
		() => {
			frappe.route_options = { role: frm.doc.name };
			frappe.set_route("List", "User", "Report");
		},
		__("View")
	);

	if (frappe.user.has_role("System Manager")) {
		frm.add_custom_button(__("Replicate Role"), () => replicate_role(frm), __("Action"));
	}
}

function replicate_role(frm) {
	const dialog = new frappe.ui.Dialog({
		title: __("Replicate Role"),
		fields: [
			{
				label: __("New Role Name"),
				fieldname: "new_role_name",
				fieldtype: "Data",
				default: frm.doc.name,
				reqd: 1,
			},
		],
		freeze: true,
		freeze_message: __("Replicating Role..."),
		primary_action_label: __("Replicate"),
		primary_action: function (values) {
			dialog.hide();
			frappe.call({
				method: "replicate_role",
				doc: frm.doc,
				args: {
					cur_role: frm.doc.name,
					new_role: values.new_role_name,
				},
				callback: function (r) {
					if (r.message) {
						frappe.set_route("Form", "Role", r.message);
						frappe.show_alert({
							message: __("New role created successfully."),
							indicator: "green",
						});
					} else if (r.exc) {
						JSON.parse(r.exc).forEach((err) => {
							frappe.show_alert({
								message: __(err),
								indicator: "red",
							});
						});
					}
				},
			});
		},
	});
	dialog.show();
}
