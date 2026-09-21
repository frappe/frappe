// The person's session: plain functions, no confirmation inside them.

import { logout as endSession } from "@framework/ui/api";

/** Ends the session, then goes to the login page with the way back to this page and query. */
export async function logout(): Promise<void> {
	await endSession();
	const back = window.location.pathname + window.location.search;
	window.location.assign(`/login?redirect-to=${encodeURIComponent(back)}`);
}
