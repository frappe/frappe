// The palette's Recent: `Route History` as `places` read it, under this tab's visits since load,
// which the server's batched write may not hold yet. One row per place, at this app's address for it.
import { computed, shallowRef } from "vue";
import type { RouteLocationNormalized, Router } from "vue-router";
import type { Addresses } from "@/addresses";
import type { Boot } from "@/boot";
import { forgetMemory } from "@/browserMemory";
import { __ } from "@/i18n";
import { canRoute, urlFor } from "@/router/routeFor";
import { visitedRoute } from "./routeHistory";

/** One list, saved view or record visit, as `places` returns it. */
export interface RecentVisit {
	/** The address `Route History` keeps: the shell base, then the path. */
	route: string;
	doctype: string;
	/** Unset or null for a list. */
	name?: string | null;
	/** A saved view's key; unset or null for anything else. */
	view?: string | null;
	title: string;
	kind: "record" | "list" | "view";
	description?: string;
	/** Milliseconds since the epoch. */
	visited: number;
}

/** A visit this tab made, translated when drawn, as the messages may load after it. */
interface TabVisit {
	route: string;
	doctype: string;
	/** None for a list. */
	name?: string;
	view?: string;
	/** A record's title or a view's label, once its page has read it. */
	title?: string;
	app?: string;
	visited: number;
}

const LIMIT = 20;

class RecentVisits {
	private readonly tab = shallowRef<TabVisit[]>([]);
	private readonly server = shallowRef<RecentVisit[]>([]);
	private readonly merged = computed(() =>
		merge(this.tab.value, this.server.value).map((visit) => ({ ...visit, route: this.addressOf(visit) }))
	);
	private readonly order = computed(
		() => new Map(this.merged.value.map((visit, index) => [visit.route, index]))
	);
	private base = "";
	private router: Router | null = null;

	/** Keeps this tab's list, view and record visits, the first one too, as `Route History` gets them. */
	track(router: Router, boot: Boot, addresses: Addresses) {
		// No record title may stay in the browser after logout.
		forgetMemory("recents");
		this.base = boot.shell_base;
		this.router = router;
		this.tab.value = [];
		const app = boot.app_title ?? boot.app ?? undefined;
		router.afterEach((to, from, failure) => {
			const route = visitedRoute(this.base, to, from, failure);
			const doctype = route && addresses.doctypeOf(String(to.params.doctype ?? ""));
			if (route && doctype)
				this.keep({ route, doctype, name: recordName(to), view: viewKey(to), app, visited: Date.now() });
		});
	}

	/** The server's visits, newest first, as `places` read them for the tab. */
	heard(visits: RecentVisit[]) {
		this.server.value = visits;
	}

	/** Newest first, one per place, this tab's visits and the server's together. */
	list(): RecentVisit[] {
		return this.merged.value;
	}

	/** 0 for the place opened last, then 1 and on; `Infinity` for one not listed. */
	recency(href: string): number {
		return this.order.value.get(href) ?? Infinity;
	}

	/** A record's title or a view's label, known once its page has read it. */
	retitle(path: string, title: string) {
		const route = this.base + path;
		const visit = this.tab.value.find((one) => one.route === route);
		if (!visit || visit.title === title) return;
		this.tab.value = this.tab.value.map((one) => (one === visit ? { ...one, title } : one));
	}

	/** In an app, its own address for the place; on the index, where the place was visited last. */
	private addressOf(visit: RecentVisit) {
		const here = this.router?.hasRoute("record") && canRoute(visit.doctype);
		return here ? urlFor(visit.doctype, visit.name, visit.view ? { view: visit.view } : {}) : visit.route;
	}

	private keep(visit: TabVisit) {
		const earlier = this.tab.value.find((one) => one.route === visit.route);
		const others = this.tab.value.filter((one) => one !== earlier);
		this.tab.value = [{ ...visit, title: earlier?.title }, ...others].slice(0, LIMIT);
	}
}

export const recentVisits = new RecentVisits();

function merge(tab: TabVisit[], server: RecentVisit[]): RecentVisit[] {
	const heard = new Map<string, RecentVisit>();
	for (const visit of server) {
		const place = placeOf(visit);
		if ((heard.get(place)?.visited ?? -Infinity) < visit.visited) heard.set(place, visit);
	}
	const ours = new Map(tab.map((visit) => [placeOf(visit), drawn(visit, heard.get(placeOf(visit)))]));
	return [...ours.values(), ...[...heard].filter(([place]) => !ours.has(place)).map(([, visit]) => visit)]
		.sort((a, b) => b.visited - a.visited)
		.slice(0, LIMIT);
}

/** A list, a view and a record are places; one visited under two prefixes is still one. */
function placeOf({ doctype, name, view }: { doctype: string; name?: string | null; view?: string | null }) {
	return JSON.stringify([doctype, name ?? null, view ?? null]);
}

/** A record says its doctype, a list, a view or a single its app, as the server writes them. */
function drawn(visit: TabVisit, heard?: RecentVisit): RecentVisit {
	const { route, doctype, name, view, app } = visit;
	const visited = Math.max(visit.visited, heard?.visited ?? 0);
	if (view) {
		const title = visit.title ?? heard?.title ?? view;
		return { route, doctype, view, title, kind: "view", description: app, visited };
	}
	if (!name) return { route, doctype, title: __(doctype), kind: "list", description: app, visited };
	const title = visit.title ?? (name === doctype ? __(doctype) : heard?.title ?? name);
	const description = name === doctype ? app : __(doctype);
	return { route, doctype, name, title, kind: "record", description, visited };
}

function recordName(to: RouteLocationNormalized) {
	return to.name === "record" ? String(to.params.name) : undefined;
}

function viewKey(to: RouteLocationNormalized) {
	return to.name === "saved-view" ? String(to.params.key) : undefined;
}
