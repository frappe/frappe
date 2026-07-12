// Per-role permissions for this doctype, rendered with frappe.ui.EmbeddedList (the same
// component the Role form's Documents tab uses). Each granted right shows as a badge.
// Reuses the Role Permissions Manager page methods — no custom backend. System-Manager-
// gated in the registry.

// Document-level rights, always shown.
const DOC_RIGHTS = ["read", "write", "create", "delete"];
// Submit-flow rights, only meaningful for submittable doctypes.
const SUBMIT_RIGHTS = ["submit", "cancel", "amend"];

frappe.doctype_settings.register("permissions", function (panel, doctype) {
	const reload = () => draw(panel, doctype);
	panel.set_view({
		title: __("Permissions"),
		description: __("Control who can access {0}.", [doctype]),
		actions: [
			{
				label: __("Add role"),
				icon: "plus",
				// Add mode of the shared editor (doctype-centric: doctype fixed, pick the role)
				// — sets the role + all its rights in one dialog.
				click: () => new frappe.ui.PermissionDialog(perm_tab(doctype, reload), {}).show(),
			},
		],
		render: reload,
	});
});

function perm_call(method, args) {
	return frappe.call({ module: "frappe.core", page: "permission_manager", method, args });
}

function draw(panel, doctype) {
	const $body = panel.body.empty();
	$(`<div class="text-muted small dts-perm-state">${__("Loading")}</div>`).appendTo($body);

	Promise.all([
		perm_call("get_permissions", { doctype }),
		// A Custom DocPerm row means this doctype's permissions diverge from standard.
		frappe.db.get_list("Custom DocPerm", {
			filters: { parent: doctype },
			fields: ["name"],
			limit: 1,
		}),
	])
		.then(([r, custom]) => {
			const perms = r.message || [];
			const is_customized = (custom || []).length > 0;
			render(panel, doctype, {
				is_customized,
				// `source` (Standard vs Custom) drives the edit dialog title + save path.
				roles: perms.map((p) => ({ ...p, source: is_customized ? "Custom" : "Standard" })),
			});
		})
		.catch(() => frappe.doctype_settings.render_error(panel, () => draw(panel, doctype)));
}

function render(panel, doctype, { roles, is_customized }) {
	const reload = () => draw(panel, doctype);
	const $body = panel.body.empty();

	if (is_customized) $body.append(customized_banner(panel, doctype, reload));

	const is_submittable = !!(frappe.get_meta(doctype) || {}).is_submittable;
	const rights = is_submittable ? DOC_RIGHTS.concat(SUBMIT_RIGHTS) : DOC_RIGHTS;

	const list = new frappe.ui.EmbeddedList({
		wrapper: $("<div></div>").appendTo($body),
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
							? ` <span class="es-badge" data-theme="blue">${__("Only own")}</span>`
							: ""
					}`,
			},
			{
				label: __("Level"),
				align: "center",
				render: (row) =>
					cint(row.permlevel) > 0
						? `<span class="es-badge" data-theme="gray">${cint(row.permlevel)}</span>`
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

	$body.append(footer(panel, doctype));
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
						"name"
					)
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
				(flag) => (data[flag] = values[flag] ? 1 : 0)
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
						"name"
					)
				)
				.then((r) => {
					const name = r.message && r.message.name;
					if (!name)
						frappe.throw(
							__("Permission row not found after conversion. Please refresh.")
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
	return `<span class="es-badge dts-perm-flag" data-theme="green">${frappe.utils.icon(
		"check",
		"xs"
	)}</span>`;
}

function customized_banner(panel, doctype, reload) {
	const $banner = $('<div class="alert alert-warning dts-perm-banner" role="alert"></div>');
	$banner.append(frappe.utils.icon("triangle-alert", "sm"));
	$('<span class="dts-perm-banner-text"></span>')
		.text(__("Permissions for this doctype have been customized."))
		.appendTo($banner);
	$('<a href="#" class="dts-perm-banner-action"></a>')
		.text(__("Reset to default"))
		.appendTo($banner)
		.on("click", (e) => {
			e.preventDefault();
			frappe.confirm(
				__("Reset {0} permissions to their default? This removes all customizations.", [
					doctype,
				]),
				() =>
					perm_call("reset", { doctype }).then(() => {
						frappe.show_alert({
							message: __("Permissions reset"),
							indicator: "green",
						});
						reload();
					})
			);
		});
	return $banner;
}

function footer(panel, doctype) {
	const $footer = $('<div class="dts-perm-footer"></div>');
	$("<span></span>").appendTo($footer); // spacer to keep the link right-aligned
	$('<a href="#" class="dts-perm-footer-link"></a>')
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
