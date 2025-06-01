import * as Sentry from "@sentry/browser";

Sentry.init({
	dsn: nts.boot.sentry_dsn,
	release: nts?.boot?.versions?.nts,
	autoSessionTracking: false,
	initialScope: {
		// don't use nts.session.user, it's set much later and will fail because of async loading
		user: { id: nts.boot.sitename },
		tags: { nts_user: nts.boot.user.name ?? "Unidentified" },
	},
	beforeSend(event, hint) {
		// Check if it was caused by nts.throw()
		if (
			hint.originalException instanceof Error &&
			hint.originalException.stack &&
			hint.originalException.stack.includes("nts.throw")
		) {
			return null;
		}
		return event;
	},
});
