import * as Sentry from "@sentry/browser";

Sentry.init({
	dsn: frappe.boot.sentry_dsn,
	release: frappe?.boot?.versions?.frappe,
	autoSessionTracking: false,
	initialScope: {
		// don't use frappe.session.user, it's set much later and will fail because of async loading
		user: { id: frappe.boot.user.name ?? "Unidentified" },
	},
});
