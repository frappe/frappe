import * as Sentry from "@sentry/browser";

Sentry.init({
	dsn: frappe.boot.sentry_dsn,
	release: frappe?.boot?.versions?.frappe,
	autoSessionTracking: false,
	initialScope: {
		// don't use frappe.session.user, it's set much later and will fail because of async loading
		user: { id: frappe.boot.sitename },
		tags: { frappe_user: frappe.boot.user.name ?? "Unidentified" },
	},
	beforeSend(event, hint) {
		// Check if it was caused by frappe.throw()
		if (
			hint.originalException instanceof Error &&
			hint.originalException.stack &&
			hint.originalException.stack.includes("frappe.throw")
		) {
			return null;
		}
		return event;
	},
});
