import * as Sentry from "@sentry/browser";

Sentry.init({
	dsn: frappe.boot.sentry_dsn,
	release: frappe?.boot?.versions?.frappe,
});
