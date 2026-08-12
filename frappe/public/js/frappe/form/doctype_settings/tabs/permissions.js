// Per-role permissions for this doctype, rendered with frappe.ui.EmbeddedList (the same
// component the Role form's Documents tab uses). Each granted right shows as a badge.
// Reuses the Role Permissions Manager page methods — no custom backend. System-Manager-
// gated in the registry.

// Document-level rights, always shown.
const DOC_RIGHTS = ["read", "write", "create", "delete"];
// Submit-flow rights, only meaningful for submittable doctypes.
const SUBMIT_RIGHTS = ["submit", "cancel", "amend"];

frappe.doctype_settings.register("permissions", function (panel, doctype) {
	panel.set_view({ render: (p) => draw(p, doctype) });
});

function perm_call(method, args) {
	return frappe.call({ module: "frappe.core", page: "permission_manager", method, args });
}

function draw(panel, doctype) {
	const $body = panel.body.empty();
	frappe.doctype_settings.render_loading($body);

	Promise.all([
		perm_call("get_permissions", { doctype }),
		// A Custom DocPerm row means this doctype's permissions diverge from standard.
		frappe.doctype_settings.get_list("Custom DocPerm", {
			filters: { parent: doctype },
			fields: ["name"],
			limit: 1,
		}),
		user_perms_apply(doctype),
	])
		.then(([r, custom, show_user_perms]) => {
			const perms = r.message || [];
			const is_customized = (custom || []).length > 0;
			render(panel, doctype, {
				is_customized,
				show_user_perms,
				// `source` (Standard vs Custom) drives the edit dialog title + save path.
				roles: perms.map((p) => ({ ...p, source: is_customized ? "Custom" : "Standard" })),
			});
		})
		.catch((err) =>
			frappe.doctype_settings.render_error(panel, () => draw(panel, doctype), err),
		);
}

function user_perms_apply(doctype) {
	return frappe
		.xcall("frappe.desk.form.linked_with.get_linked_doctypes", {
			doctype,
			without_ignore_user_permissions_enabled: 1,
		})
		.then((map) => !!map && Object.keys(map).length > 0)
		.catch(() => false);
}

function render(panel, doctype, { roles, is_customized, show_user_perms }) {
	const reload = () => draw(panel, doctype);
	const $body = panel.body.empty();

	// ── Roles: who can access this doctype, by role ──
	const roles_sec = frappe.doctype_settings.section($body, {
		title: __("Roles"),
		description: __("Control who can access {0}, by role.", [doctype]),
	});
	frappe.ui
		.button({
			label: __("Add role"),
			icon: "plus",
			onclick: () => new frappe.ui.PermissionDialog(perm_tab(doctype, reload), {}).show(),
		})
		.appendTo(roles_sec.$actions);
	if (is_customized) roles_sec.$body.append(customized_banner(panel, doctype, reload));
	render_roles_list(roles_sec.$body, doctype, roles, reload);
	roles_sec.$body.append(footer(panel, doctype));

	if (show_user_perms) render_user_perms(panel, $body, doctype);
}

function render_roles_list($container, doctype, roles, reload) {
	const is_submittable = !!(frappe.get_meta(doctype) || {}).is_submittable;
	const rights = is_submittable ? DOC_RIGHTS.concat(SUBMIT_RIGHTS) : DOC_RIGHTS;

	const list = new frappe.ui.EmbeddedList({
		wrapper: $("<div></div>").appendTo($container),
		empty_message: __("No roles have access yet."),
		get_data: () => Promise.resolve(roles),
		// Clicking a row opens the shared permission editor for that role (same dialog
		// the Role form's Documents tab uses).
		on_row_click: (row) =>
			new frappe.ui.PermissionDialog(perm_tab(doctype, reload), { row }).show(),
		columns: [
			{
				label: __("Role"),
				fieldname: "role",
				// Show an "Only own" badge beside the role when its rights are creator-scoped.
				render: (row) =>
					`${frappe.utils.escape_html(row.role)}${
						cint(row.if_owner)
							? ` ${frappe.ui.badge.html({ label: __("Only own"), theme: "blue" })}`
							: ""
					}`,
			},
			{
				label: __("Level"),
				align: "center",
				render: (row) =>
					cint(row.permlevel) > 0
						? frappe.ui.badge.html({ label: String(cint(row.permlevel)) })
						: "",
			},
			...rights.map((r) => ({
				label: __(frappe.perm_editor.capitalize(r)),
				align: "center",
				// At permlevel > 0 only read/write/mask apply; hide other flags for those rows.
				render: (row) =>
					cint(row.permlevel) > 0 && !frappe.perm_editor.PERMLEVEL_FLAGS.includes(r)
						? ""
						: cint(row[r])
							? flag_badge()
							: "",
			})),
		],
	});
	list.refresh();
}


function render_user_perms(panel, $parent, doctype) {
	const sec = frappe.doctype_settings.section($parent, {
		title: __("User Permissions"),
		description: __("Restrict specific users to specific {0} records.", [doctype]),
	});
	let list;
	const refresh = () => list.refresh();
	frappe.ui
		.button({
			label: __("Add"),
			icon: "plus",
			onclick: () => add_user_permission(doctype, refresh),
		})
		.appendTo(sec.$actions);

	list = new frappe.ui.EmbeddedList({
		wrapper: $("<div></div>").appendTo(sec.$body),
		empty_message: __("No user is restricted to specific {0} records yet.", [doctype]),
		get_data: () =>
			frappe.doctype_settings.get_list("User Permission", {
				filters: { allow: doctype },
				fields: [
					"name",
					"user",
					"for_value",
					"applicable_for",
					"apply_to_all_doctypes",
					"is_default",
				],
				limit: 0,
			}),
		// Row click opens the full User Permission form for editing.
		on_row_click: (row) => {
			panel.dialog.hide();
			frappe.set_route("Form", "User Permission", row.name);
		},
		columns: [
			{
				label: __("User"),
				fieldname: "user",
				// Flag the user's default value with a badge beside their id.
				render: (row) =>
					`${frappe.utils.escape_html(row.user)}${
						cint(row.is_default)
							? ` ${frappe.ui.badge.html({ label: __("Default"), theme: "green" })}`
							: ""
					}`,
			},
			{ label: __("For Value"), fieldname: "for_value" },
			{
				label: __("Applicable For"),
				render: (row) =>
					cint(row.apply_to_all_doctypes)
						? frappe.ui.badge.html({ label: __("All doctypes") })
						: row.applicable_for
							? frappe.utils.escape_html(row.applicable_for)
							: "",
			},
			{
				type: "actions",
				actions: [
					{
						icon: "trash-2",
						label: __("Delete"),
						danger: true,
						confirm: __("Delete this user permission?"),
						action: (row, refresh) =>
							frappe.db.delete_doc("User Permission", row.name).then(() => {
								frappe.show_alert({ message: __("Deleted"), indicator: "green" });
								refresh();
							}),
					},
				],
			},
		],
	});
	list.refresh();
}

// Quick-add a User Permission (user + a record of this doctype). Standard insert.
function add_user_permission(doctype, refresh) {
	const dialog = new frappe.ui.Dialog({
		title: __("Add User Permission"),
		fields: [
			{ fieldtype: "Link", fieldname: "user", label: __("User"), options: "User", reqd: 1 },
			{
				fieldtype: "Link",
				fieldname: "for_value",
				label: __("For Value"),
				options: doctype,
				reqd: 1,
			},
			{
				fieldtype: "Check",
				fieldname: "is_default",
				label: __("Mark as default"),
				description: __("Use this value by default in new documents."),
			},
		],
		primary_action_label: __("Add"),
		primary_action: (values) => {
			frappe.db
				.insert({
					doctype: "User Permission",
					user: values.user,
					allow: doctype,
					for_value: values.for_value,
					is_default: values.is_default ? 1 : 0,
				})
				.then(() => {
					dialog.hide();
					frappe.show_alert({
						message: __("User permission added"),
						indicator: "green",
					});
					refresh();
				});
		},
	});
	dialog.show();
}

// Adapter the shared PermissionDialog drives: doctype-scoped (role varies per row),
// reusing the same permission_manager save/remove paths as the Role form's tab.
function perm_tab(doctype, reload) {
	return {
		// Doctype-centric: the doctype is fixed and the role varies (the opposite of role.js).
		// The dialog reads `doctype` (for add mode) and `role` stays null.
		role: null,
		doctype,
		refresh: () => reload(),
		// Add mode: create the role's permission row, then apply the chosen flags.
		create(values) {
			const permlevel = cint(values.permlevel);
			return perm_call("add", { parent: doctype, role: values.role, permlevel })
				.then(() =>
					frappe.db.get_value(
						"Custom DocPerm",
						{ parent: doctype, role: values.role, permlevel, if_owner: 0 },
						"name",
					),
				)
				.then((r) => {
					const name = r.message && r.message.name;
					if (!name)
						frappe.throw(__("Permission row not found after add. Please refresh."));
					return frappe.db.set_value("Custom DocPerm", name, this.perm_data(values));
				});
		},
		perm_data(values) {
			const data = {};
			["if_owner", ...frappe.perm_editor.ALL_PERM_FLAGS].forEach(
				(flag) => (data[flag] = values[flag] ? 1 : 0),
			);
			return data;
		},
		update(row, values) {
			const data = this.perm_data(values);
			if (row.source === "Custom") {
				return frappe.db.set_value("Custom DocPerm", row.name, data);
			}
			// Standard row: the manager's update converts DocPerm → Custom DocPerm (using
			// "read" as a harmless trigger flag), then we set the rest on the new row.
			return perm_call("update", {
				doctype,
				role: row.role,
				permlevel: row.permlevel,
				ptype: "read",
				value: data.read,
				if_owner: row.if_owner || 0,
			})
				.then(() =>
					frappe.db.get_value(
						"Custom DocPerm",
						{
							parent: doctype,
							role: row.role,
							permlevel: row.permlevel,
							if_owner: row.if_owner || 0,
						},
						"name",
					),
				)
				.then((r) => {
					const name = r.message && r.message.name;
					if (!name)
						frappe.throw(
							__("Permission row not found after conversion. Please refresh."),
						);
					return frappe.db.set_value("Custom DocPerm", name, data);
				});
		},
		remove(row) {
			return perm_call("remove", {
				doctype,
				role: row.role,
				permlevel: row.permlevel,
				if_owner: row.if_owner || 0,
			});
		},
	};
}

// A granted right is shown as a green badge.
function flag_badge() {
	return frappe.ui.badge.html({
		theme: "green",
		icon: "check",
		css_class: "dts-perm-flag",
		title: __("Granted"),
	});
}

function customized_banner(panel, doctype, reload) {
	const reset = () =>
		frappe.confirm(
			__("Reset {0} permissions to their default? This removes all customizations.", [
				doctype,
			]),
			() =>
				perm_call("reset", { doctype }).then(() => {
					frappe.show_alert({ message: __("Permissions reset"), indicator: "green" });
					reload();
				}),
		);

	return frappe.ui
		.alert({
			title: __("Permissions for this doctype have been customized."),
			theme: "yellow",
			footer: frappe.ui.button({
				label: __("Reset to default"),
				size: "sm",
				variant: "outline",
				onclick: reset,
			}),
		})
		.addClass("dts-perm-banner");
}

function footer(panel, doctype) {
	const $footer = $('<div class="dts-perm-footer"></div>');
	$("<span></span>").appendTo($footer); // spacer to keep the link right-aligned
	$('<a href="#" class="dts-perm-footer-link text-base-medium"></a>')
		.append($("<span></span>").text(__("Open Role Permissions Manager")))
		.append(frappe.utils.icon("external-link", "sm"))
		.appendTo($footer)
		.on("click", (e) => {
			e.preventDefault();
			panel.dialog.hide();
			frappe.set_route("permission-manager", { doctype });
		});
	return $footer;
}
