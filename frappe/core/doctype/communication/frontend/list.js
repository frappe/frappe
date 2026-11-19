import { __ } from "frappe/i18n";

const MARK_READ_UNREAD = "frappe.email.inbox.mark_read_unread";

export default {
	onRefresh(page) {
		page.bulkActions.add({
			name: "mark_as_read",
			label: __("Mark as Read"),
			icon: "lucide-mail-open",
			run: (page) => page.callSelected(MARK_READ_UNREAD, { action: "Read" }),
		});
		page.bulkActions.add({
			name: "mark_as_unread",
			label: __("Mark as Unread"),
			icon: "lucide-mail",
			run: (page) => page.callSelected(MARK_READ_UNREAD, { action: "Unread" }),
		});
	},
};
