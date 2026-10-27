// Writes each list and record visit to `Route History`, as desk v1 does; the index's Recent reads it.
import { debounce } from "frappe-ui";
import type { NavigationFailure, RouteLocationNormalized, Router } from "vue-router";
import { runMethod } from "@framework/ui/api";

const INSERT_METHOD = "frappe.desk.doctype.route_history.route_history.deferred_insert";
const RECORDED_ROUTES = new Set(["list", "record"]);
const QUIET_MS = 10_000;

/** Queues each list and record address the router lands on; sends after 10 s of quiet, or as the tab hides. */
export function recordRouteHistory(router: Router, base: string) {
	let queue: { route: string }[] = [];

	// Kept alive, so a full load that starts while it is in flight does not drop the batch.
	const send = () => {
		if (!queue.length) return;
		const routes = queue;
		queue = [];
		// A lost visit costs one Recent row; a retry queue would grow while the site is read-only.
		runMethod(INSERT_METHOD, { routes }, { nullable: true, keepalive: true }).catch(() => {});
	};
	const sendLater = debounce(send, QUIET_MS);

	router.afterEach((to, from, failure) => {
		const route = visitedRoute(base, to, from, failure);
		if (!route) return;
		queue.push({ route });
		sendLater();
	});

	// A full load to another app or the index would drop the queue with the page.
	document.addEventListener("visibilitychange", () => {
		if (document.visibilityState !== "hidden") return;
		sendLater.cancel();
		send();
	});
}

/** The address `Route History` keeps for a navigation, or `null` for one that is no list or record visit. */
export function visitedRoute(
	base: string,
	to: RouteLocationNormalized,
	from: RouteLocationNormalized,
	failure?: NavigationFailure | void
) {
	if (failure || !RECORDED_ROUTES.has(String(to.name)) || to.path === from.path) return null;
	return `${base}${to.path}`;
}
