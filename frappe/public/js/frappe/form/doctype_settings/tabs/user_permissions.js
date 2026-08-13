frappe.doctype_settings.register("user-permissions", function (panel, doctype) {
	let list;
	panel.set_view({
		title: __("User Permissions"),
		description: __("Restrict specific users to specific {0} records.", [doctype]),
		// Add sits top-right by the title (like the Roles tab); the list keeps its search box.
		actions: [
			{
				label: __("Add"),
				icon: "plus",
				click: () => add_user_permission(doctype, () => list && list.refresh()),
			},
		],
		render: (p) => {
			list = draw(p, doctype);
		},
	});
});

function draw(panel, doctype) {
	const open = (name) => {
		panel.dialog.hide();
		frappe.set_route("Form", "User Permission", name);
	};

	const list = new frappe.ui.EmbeddedList({
		wrapper: $('<div class="dts-user-permissions-list"></div>').appendTo(panel.body.empty()),
		empty_icon: "user-lock",
		empty_message: __("No user permissions yet."),
		get_data: () =>
			frappe
				.call({
					method: "frappe.core.doctype.user_permission.user_permission.get_user_permission_list",
					args: { allow: doctype },
				})
				.then((r) => r.message || []),
		columns: [
			{
				label: __("User"),
				render: (row) => user_cell(row),
				on_click: (row) => open(row.name),
			},
			{ label: __("For Value"), fieldname: "for_value" },
			{
				label: __("Applicable For"),
				render: (row) => applicable_badge(row),
			},
			{
				type: "actions",
				label: "",
				actions: [
					{
						label: __("Delete"),
						icon: "trash-2",
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
	return list;
}

function user_cell(row) {
	const esc = frappe.utils.escape_html;
	const name = row.full_name || row.user;
	const avatar = frappe.ui.avatar.html({ label: name, image: row.user_image, size: "lg" });
	const email = row.full_name
		? `<div class="text-ink-gray-5 text-xs truncate">${esc(row.user)}</div>`
		: "";
	return `<div class="flex items-center gap-2">
		${avatar}
		<div class="min-w-0">
			<div class="text-ink-gray-8 text-base-medium truncate">${esc(name)}</div>
			${email}
		</div>
	</div>`;
}

function applicable_badge(row) {
	if (cint(row.apply_to_all_doctypes)) {
		return frappe.ui.badge.html({ label: __("All doctypes"), theme: "blue" });
	}
	if (row.applicable_for) {
		return frappe.ui.badge.html({ label: frappe.utils.escape_html(row.applicable_for) });
	}
	return "";
}

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
			{ fieldtype: "Section Break", label: __("Advanced Control"), collapsible: 1 },
			{
				fieldtype: "Check",
				fieldname: "apply_to_all_doctypes",
				label: __("Apply To All Document Types"),
				default: 1,
			},
			{
				fieldtype: "Link",
				fieldname: "applicable_for",
				label: __("Applicable For"),
				options: "DocType",
				depends_on: "eval:!doc.apply_to_all_doctypes",
				mandatory_depends_on: "eval:!doc.apply_to_all_doctypes",
				get_query: () => ({
					query: "frappe.core.doctype.user_permission.user_permission.get_applicable_for_doctype_list",
					filters: { doctype },
				}),
			},
			// Hide Descendants only applies to tree (nested-set) doctypes — same gate as the form.
			...((frappe.boot.nested_set_doctypes || []).includes(doctype)
				? [
						{
							fieldtype: "Check",
							fieldname: "hide_descendants",
							label: __("Hide Descendants"),
						},
				  ]
				: []),
		],
		primary_action_label: __("Add"),
		primary_action: (values) => {
			const apply_to_all = values.apply_to_all_doctypes ? 1 : 0;
			// Reuse the canonical create path: it clears rows that would go stale on the
			// apply-to-all ↔ specific-doctype switch (remove_applicable / remove_apply_to_all).
			frappe
				.call({
					method: "frappe.core.doctype.user_permission.user_permission.add_user_permissions",
					args: {
						data: {
							user: values.user,
							doctype: doctype,
							docname: values.for_value,
							apply_to_all_doctypes: apply_to_all,
							applicable_doctypes:
								!apply_to_all && values.applicable_for
									? [values.applicable_for]
									: [],
							is_default: 0,
							hide_descendants: values.hide_descendants ? 1 : 0,
						},
					},
				})
				.then((r) => {
					dialog.hide();
					frappe.show_alert(
						r.message
							? { message: __("User permission added"), indicator: "green" }
							: {
									message: __("User permission already exists"),
									indicator: "orange",
							  }
					);
					refresh();
				});
		},
	});
	dialog.show();
}
