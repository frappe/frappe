import * as Sentry from "@sentry/browser";

Sentry.init({
	dsn: frappe.boot.sentry,
	release: frappe?.boot?.versions?.frappe,
});
