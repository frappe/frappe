// The places and records this user opened last, by any route, kept in this browser for the palette.
import { shallowRef } from "vue";
import type { RouteLocationNormalized, Router } from "vue-router";
import type { Addresses } from "@/addresses";
import type { Boot } from "@/boot";
import { browserMemory, type BrowserMemory } from "@/browserMemory";

export interface Recent {
	href: string;
	label: string;
	description?: string;
	kind: "record" | "list" | "page";
}

const LIMIT = 20;
const RECORD_ROUTES = new Set(["record", "standard-record"]);
const LIST_ROUTES = new Set(["list", "standard-list"]);
const KINDS = new Set(["record", "list", "page"]);

class Recents {
	private readonly kept = shallowRef<Recent[]>([]);
	private memory: BrowserMemory<Recent[]> | null = null;
	private router: Router | null = null;

	/** Keeps every route that opens a place or a record, from the first one on. */
	track(router: Router, boot: Boot, addresses: Addresses) {
		this.router = router;
		this.memory = browserMemory("recents", boot.session.user.name, isRecentList);
		this.kept.value = this.memory.recall() ?? [];
		router.afterEach((to, _from, failure) => {
			if (failure) return;
			const recent = recentOf(to, router, boot, addresses);
			if (recent) this.keep(recent);
		});
	}

	/** Newest first. */
	list(): Recent[] {
		return this.kept.value;
	}

	/** 0 for the place opened last, then 1 and on; `Infinity` for one not kept. */
	recency(href: string): number {
		const index = this.kept.value.findIndex((recent) => recent.href === href);
		return index < 0 ? Infinity : index;
	}

	/** A record's title, known once its page has read it. */
	retitle(path: string, label: string) {
		if (!this.router || !label) return;
		const href = this.router.resolve(path).href;
		const stored = this.stored();
		const recent = stored.find((one) => one.href === href);
		if (!recent || recent.label === label) return;
		this.write(stored.map((one) => (one === recent ? { ...one, label } : one)));
	}

	private keep(recent: Recent) {
		const stored = this.stored();
		const earlier = stored.find((one) => one.href === recent.href);
		// A record's title outlives the visit; the route alone only knows its name.
		const label = recent.kind === "record" && earlier ? earlier.label : recent.label;
		const others = stored.filter((one) => one !== earlier);
		this.write([{ ...recent, label }, ...others].slice(0, LIMIT));
	}

	// Read again before each write, so another tab's visits are not lost.
	private stored(): Recent[] {
		return this.memory?.recall() ?? this.kept.value;
	}

	private write(list: Recent[]) {
		this.kept.value = list;
		this.memory?.remember(list);
	}
}

export const recents = new Recents();

function recentOf(
	to: RouteLocationNormalized,
	router: Router,
	boot: Boot,
	addresses: Addresses
): Recent | null {
	const name = String(to.name ?? "");
	const href = router.resolve(to.path).href;
	const app = boot.app_title ?? boot.app ?? undefined;
	if (name.startsWith("page:") && typeof to.meta.title === "string")
		return { href, label: to.meta.title, description: app, kind: "page" };

	const doctype = addresses.doctypeOf(String(to.params.doctype ?? ""));
	if (!doctype) return null;
	if (RECORD_ROUTES.has(name)) {
		const record = String(to.params.name);
		return record === doctype
			? { href, label: doctype, description: app, kind: "record" }
			: { href, label: record, description: doctype, kind: "record" };
	}
	if (LIST_ROUTES.has(name)) return { href, label: doctype, description: app, kind: "list" };
	return null;
}

function isRecentList(value: unknown): value is Recent[] {
	return Array.isArray(value) && value.every(isRecent);
}

function isRecent(value: unknown): value is Recent {
	const recent = value as Recent;
	return (
		typeof recent?.href === "string" &&
		typeof recent.label === "string" &&
		KINDS.has(recent.kind)
	);
}
