import { __ } from "frappe/i18n";

export default {
	onRefresh(page) {
		page.rowActions.add({
			name: "open_reference",
			label: __("Open Reference"),
			icon: "lucide-external-link",
			fields: ["reference_type", "reference_name"],
			when: (page, row) => Boolean(row.reference_type && row.reference_name),
			run: (page, row) => page.open(row.reference_type, row.reference_name),
		});
	},
};
