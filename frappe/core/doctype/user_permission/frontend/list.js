import { __ } from "frappe/i18n";

const CLEAR_FIELDS = [
	{ fieldname: "user", fieldtype: "Link", label: __("For User"), options: "User", reqd: 1 },
	{
		fieldname: "for_doctype",
		fieldtype: "Link",
		label: __("For Document Type"),
		options: "DocType",
		reqd: 1,
	},
];

export default {
	onRefresh(page) {
		page.header.add({
			name: "clear_user_permissions",
			label: __("Bulk Delete"),
			icon: "lucide-trash-2",
			when: (page) => page.roles.includes("System Manager"),
			run: clearUserPermissions,
		});
	},
};

async function clearUserPermissions(page) {
	const values = await page.dialog.form({
		title: __("Clear User Permissions"),
		fields: CLEAR_FIELDS,
		submitLabel: __("Delete"),
	});
	if (!values) return;
	const sure = await page.dialog.danger({
		title: __("Clear User Permissions"),
		message: __("Delete every User Permission of {0} on {1}?", [
			values.user,
			values.for_doctype,
		]),
		confirmLabel: __("Delete"),
	});
	if (!sure) return;
	const count = await page.call(
		"frappe.core.doctype.user_permission.user_permission.clear_user_permissions",
		values
	);
	page.toast.info(deletedMessage(count || 0));
	page.reload();
}

function deletedMessage(count) {
	if (!count) return __("No records deleted");
	return count === 1 ? __("1 record deleted") : __("{0} records deleted", [count]);
}
