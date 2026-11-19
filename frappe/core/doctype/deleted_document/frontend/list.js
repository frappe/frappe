import { __ } from "frappe/i18n";

export default {
	onRefresh(page) {
		page.bulkActions.add({
			name: "restore",
			label: __("Restore"),
			icon: "lucide-archive-restore",
			when: (page) => page.roles.includes("System Manager"),
			run: (page) =>
				page.callSelected(
					"frappe.core.doctype.deleted_document.deleted_document.restore_record"
				),
		});
	},
};
