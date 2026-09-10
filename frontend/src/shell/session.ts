// The person's session: plain functions, no confirmation inside them.

import { call } from "frappe-ui";

/** Ends the session, then goes to the login page with the way back to this page and query. */
export async function logout(): Promise<void> {
	await call("logout");
	const back = window.location.pathname + window.location.search;
	window.location.assign(`/login?redirect-to=${encodeURIComponent(back)}`);
}
