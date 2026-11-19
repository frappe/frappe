import { currentSession } from "@framework/ui";
import { __ } from "frappe/i18n";
import { ref } from "vue";

const STATUS_THEMES = {
	Sent: "green",
	Sending: "blue",
	"Not Sent": "gray",
	Error: "red",
	Expired: "orange",
};
const EMAIL_QUEUE = "frappe.email.doctype.email_queue.email_queue";

export default {
	onRefresh(page) {
		page.columns.update("status", {
			badge: (row) =>
				row.status && {
					label: __(row.status),
					theme: STATUS_THEMES[row.status],
					filters: [["status", "=", row.status]],
				},
		});
		page.bulkActions.add({
			name: "retry_sending",
			label: __("Retry Sending"),
			icon: "lucide-rotate-cw",
			run: (page) => page.callSelected(`${EMAIL_QUEUE}.retry_record`),
		});
		page.header.add({
			name: "suspend_sending",
			label: __("Suspend Sending"),
			when: (page) => isSystemManager(page) && !isSuspended(),
			run: (page) => toggleSending(page, 0),
		});
		page.header.add({
			name: "resume_sending",
			label: __("Resume Sending"),
			when: (page) => isSystemManager(page) && isSuspended(),
			run: (page) => toggleSending(page, 1),
		});
	},
};

// The session's defaults hold the value from boot; a toggle here outdates them.
const suspendedNow = ref(null);

function isSuspended() {
	return suspendedNow.value ?? Number(currentSession()?.defaults?.suspend_email_queue) === 1;
}

function isSystemManager(page) {
	return page.roles.includes("System Manager");
}

async function toggleSending(page, enable) {
	await page.call(`${EMAIL_QUEUE}.toggle_sending`, { enable });
	suspendedNow.value = !enable;
	page.toast.success(enable ? __("Sending resumed") : __("Sending suspended"));
}
