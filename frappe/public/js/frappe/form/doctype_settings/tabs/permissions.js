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
		description: __("Who can access {0}, by role.", [doctype]),
		actions: [
			{ label: __("Add role"), icon: "add", primary: true, click: () => add_role(panel, doctype, reload) },
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
		frappe.db.get_list("Custom DocPerm", { filters: { parent: doctype }, fields: ["name"], limit: 1 }),
	])
		.then(([r, custom]) => {
			const perms = r.message || [];
			render(panel, doctype, {
				// `source` (Standard vs Custom) drives the edit dialog title + save path.
				roles: perms
					.filter((p) => cint(p.permlevel) === 0)
					.map((p) => ({ ...p, source: p.parenttype ? "Standard" : "Custom" })),
				is_customized: (custom || []).length > 0,
				has_field_level: perms.some((p) => cint(p.permlevel) > 0),
			});
		})
		.catch(() => {
			panel.body.empty();
			$(`<div class="text-muted small dts-perm-state">${__("Could not load permissions.")}</div>`).appendTo(
				panel.body
			);
		});
}

function render(panel, doctype, { roles, is_customized, has_field_level }) {
	const reload = () => draw(panel, doctype);
	const $body = panel.body.empty();

	if (is_customized) $body.append(customized_banner(panel, doctype, reload));

	const is_submittable = !!(frappe.get_meta(doctype) || {}).is_submittable;
	const rights = is_submittable ? DOC_RIGHTS.concat(SUBMIT_RIGHTS) : DOC_RIGHTS;

	const list = new frappe.ui.EmbeddedList({
		wrapper: $('<div></div>').appendTo($body),
		empty_message: __("No roles have access yet."),
		get_data: () => Promise.resolve(roles),
		// Clicking a row opens the shared permission editor for that role (same dialog
		// the Role form's Documents tab uses).
		on_row_click: (row) => new frappe.ui.PermissionDialog(perm_tab(doctype, reload), { row }).show(),
		columns: [
			{ label: __("Role"), fieldname: "role" },
			...rights.map((r) => ({
				label: __(frappe.perm_editor.capitalize(r)),
				align: "center",
				render: (row) => (cint(row[r]) ? flag_badge() : ""),
			})),
			{
				label: __("Only own"),
				align: "center",
				render: (row) =>
					cint(row.if_owner)
						? `<span class="es-badge" data-theme="blue">${__("Yes")}</span>`
						: `<span class="text-muted">${__("No")}</span>`,
			},
		],
	});
	list.refresh();

	$body.append(footer(panel, doctype, has_field_level));
}

// Adapter the shared PermissionDialog drives: doctype-scoped (role varies per row),
// reusing the same permission_manager save/remove paths as the Role form's tab.
function perm_tab(doctype, reload) {
	return {
		// Only used by the dialog's add mode (which this tab doesn't open).
		role: null,
		refresh: () => reload(),
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
						{ parent: doctype, role: row.role, permlevel: row.permlevel, if_owner: row.if_owner || 0 },
						"name"
					)
				)
				.then((r) => {
					const name = r.message && r.message.name;
					if (!name) frappe.throw(__("Permission row not found after conversion. Please refresh."));
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
		"tick",
		"xs"
	)}</span>`;
}

function customized_banner(panel, doctype, reload) {
	const $banner = $('<div class="alert alert-warning dts-perm-banner" role="alert"></div>');
	$banner.append(frappe.utils.icon("solid-warning", "sm"));
	$('<span class="dts-perm-banner-text"></span>')
		.text(__("Permissions for this doctype have been customized."))
		.appendTo($banner);
	$('<a href="#" class="dts-perm-banner-action"></a>')
		.text(__("Reset to default"))
		.appendTo($banner)
		.on("click", (e) => {
			e.preventDefault();
			frappe.confirm(
				__("Reset {0} permissions to their default? This removes all customizations.", [doctype]),
				() =>
					perm_call("reset", { doctype }).then(() => {
						frappe.show_alert({ message: __("Permissions reset"), indicator: "green" });
						reload();
					})
			);
		});
	return $banner;
}

function footer(panel, doctype, has_field_level) {
	const $footer = $('<div class="dts-perm-footer"></div>');
	if (has_field_level) {
		const $note = $('<span class="dts-perm-footer-note"></span>').appendTo($footer);
		$note.append(frappe.utils.icon("list", "sm"));
		$('<span></span>').text(__("Field-level rules exist for this doctype")).appendTo($note);
	} else {
		$('<span></span>').appendTo($footer); // spacer to keep the link right-aligned
	}
	$('<a href="#" class="dts-perm-footer-link"></a>')
		.append($("<span></span>").text(__("Open Role Permissions Manager")))
		.append(frappe.utils.icon("link-url", "sm"))
		.appendTo($footer)
		.on("click", (e) => {
			e.preventDefault();
			panel.dialog.hide();
			frappe.set_route("permission-manager", { doctype });
		});
	return $footer;
}

// Adds a role at permlevel 0 via the manager's `add`.
function add_role(panel, doctype, reload) {
	const d = new frappe.ui.Dialog({
		title: __("Add role"),
		fields: [
			{
				fieldtype: "Link",
				options: "Role",
				label: __("Role"),
				fieldname: "role",
				reqd: 1,
				get_query: () => ({ filters: { disabled: 0 } }),
			},
		],
		primary_action_label: __("Add"),
		primary_action: ({ role }) => {
			d.hide();
			perm_call("add", { parent: doctype, role, permlevel: 0 }).then(() => {
				frappe.show_alert({ message: __("Role added"), indicator: "green" });
				reload();
			});
		},
	});
	d.show();
}
