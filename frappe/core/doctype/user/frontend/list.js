import { __ } from "frappe/i18n";

const ROLES_FIELD = {
	fieldname: "roles",
	fieldtype: "Table MultiSelect",
	label: __("Roles"),
	options: "Has Role",
	child_fields: [
		{
			fieldname: "role",
			fieldtype: "Link",
			label: __("Role"),
			options: "Role",
			in_list_view: 1,
		},
	],
	reqd: 1,
};

async function changeRoles(page, { method, title, submitLabel, theme }) {
	const values = await page.dialog.form({
		title,
		fields: [ROLES_FIELD],
		actions: [{ label: submitLabel, variant: "solid", theme }],
	});
	if (!values) return;

	const roles = values.roles.map((row) => row.role).filter(Boolean);
	await page.callSelected(`frappe.core.doctype.user.user.${method}`, { roles });
}

export default {
	onRefresh(page) {
		page.bulkActions.add({
			name: "add_roles",
			label: __("Add Roles"),
			icon: "lucide-shield-plus",
			right: "write",
			run: (page) =>
				changeRoles(page, {
					method: "add_roles_to_user",
					title: __("Add Roles"),
					submitLabel: __("Add"),
				}),
		});
		page.bulkActions.add({
			name: "remove_roles",
			label: __("Remove Roles"),
			icon: "lucide-shield-minus",
			right: "write",
			run: (page) =>
				changeRoles(page, {
					method: "remove_roles_from_user",
					title: __("Remove Roles"),
					submitLabel: __("Remove"),
					theme: "red",
				}),
		});
	},
};
