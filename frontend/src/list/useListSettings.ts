// One doctype's stored list settings: the site row and the person's own, fetched beside meta once
// and again after a DocType change, written back silently. A write's response replaces both rows.
// The same read says which of the list and its saved views the person starred; a star toggles in turn with the writes.
import { runMethod } from "@framework/ui/api";
import { landFresh } from "@framework/ui/utils";
import { computed, getCurrentScope, onScopeDispose, ref, type ComputedRef, type Ref } from "vue";
import type { ListSettings, ListSettingsKey } from "./storedSettings";

const API = "frappe.desk.doctype.doctype_view.api";
const TOGGLE_FAVOURITE = "frappe.desk.doctype.favourite.favourite.toggle_favourite";
export const VIEW_TYPE = "List";
/** Column edits in the popover come in bursts; one write carries the burst. */
export const WRITE_DEBOUNCE_MS = 500;

export type Scope = "user" | "site";

/** Whether the person starred the list itself, and the keys of the saved views they starred. */
export interface ListFavourites {
	list: boolean;
	views: string[];
}

export interface ListSettingsHandle {
	loaded: ComputedRef<boolean>;
	/** The site row under the person's own, key by key. */
	stored: ComputedRef<ListSettings>;
	has: (scope: Scope, key: ListSettingsKey) => boolean;
	/** Debounced; a later patch in the window joins the same write. */
	save: (patch: ListSettings) => void;
	reset: (key: ListSettingsKey) => Promise<void>;
	saveForSite: (patch: ListSettings) => Promise<void>;
	resetForSite: (key: ListSettingsKey) => Promise<void>;
	/** Sends a waiting write now. */
	flush: () => Promise<void>;
	/** True while stale settings show and fresh ones are read. */
	refreshing: ComputedRef<boolean>;
	/** Resolves once the fresh read of stale settings has arrived, shown or held. */
	refreshed: () => Promise<void>;
	/** Null until a settings read succeeds: the star cannot be drawn without it. */
	favourites: ComputedRef<ListFavourites | null>;
	/** Stars or unstars the list, or its saved view with the key `view`; rejects with the server's refusal. */
	toggleFavourite: (view: string | null) => Promise<void>;
}

interface Tiers {
	site: ListSettings | null;
	user: ListSettings | null;
}

interface Entry {
	tiers: Ref<Tiers>;
	favourites: Ref<ListFavourites | null>;
	loaded: Ref<boolean>;
	pending: ListSettings | null;
	/** How many times each key was reset; a failed patch comes back only for keys reset no further. */
	resets: Partial<Record<ListSettingsKey, number>>;
	timer: ReturnType<typeof setTimeout> | null;
	/** Writes go out one after another, so a late response cannot overwrite a later one. */
	queue: Promise<void>;
	/** The DocType changed; a holder keeps this entry, the next caller gets a new one seeded from it. */
	stale: boolean;
	refreshing: Ref<boolean>;
	refreshed: Promise<void>;
}

const entries = new Map<string, Entry>();

export function useListSettings(doctype: string): ListSettingsHandle {
	const entry = entryFor(doctype);
	const address = { doctype, type: VIEW_TYPE };

	const flush = () => flushEntry(entry, doctype);

	function save(patch: ListSettings) {
		entry.pending = { ...entry.pending, ...patch };
		if (entry.timer) clearTimeout(entry.timer);
		entry.timer = setTimeout(flush, WRITE_DEBOUNCE_MS);
	}

	async function reset(key: ListSettingsKey) {
		if (entry.pending) delete entry.pending[key];
		entry.resets[key] = (entry.resets[key] ?? 0) + 1;
		await flush();
		await write(entry, () => send(`${API}.reset`, { ...address, scope: "user", key }));
	}

	async function saveForSite(patch: ListSettings) {
		await write(entry, () => send(`${API}.save`, { ...address, scope: "site", settings: patch }));
	}

	async function resetForSite(key: ListSettingsKey) {
		await write(entry, () => send(`${API}.reset`, { ...address, scope: "site", key }));
	}

	if (getCurrentScope()) onScopeDispose(() => void flush());

	return {
		loaded: computed(() => entry.loaded.value),
		stored: computed(() => ({ ...entry.tiers.value.site, ...entry.tiers.value.user })),
		has: (scope, key) => {
			if (scope === "user" && entry.pending && key in entry.pending) return true;
			const row = entry.tiers.value[scope];
			return row != null && key in row;
		},
		save,
		reset,
		saveForSite,
		resetForSite,
		flush,
		refreshing: computed(() => entry.refreshing.value),
		refreshed: () => entry.refreshed,
		favourites: computed(() => entry.favourites.value),
		toggleFavourite: (view) => toggleFavourite(entry, doctype, view),
	};
}

/** Marks the doctype's settings stale; a waiting write goes out first, and the next caller reads after it. */
export function markListSettingsStale(doctype: string): void {
	const entry = entries.get(doctype);
	if (!entry) return;
	entry.stale = true;
	void flushEntry(entry, doctype);
}

/** Drops every fetched row, so one test's settings cannot reach the next. */
export function resetListSettings(): void {
	for (const entry of entries.values()) if (entry.timer) clearTimeout(entry.timer);
	entries.clear();
}

function entryFor(doctype: string): Entry {
	const existing = entries.get(doctype);
	if (existing && !existing.stale) return existing;
	const seeded = existing?.loaded.value ?? false;
	const entry: Entry = {
		tiers: ref(seeded ? existing!.tiers.value : { site: null, user: null }),
		favourites: ref(seeded ? existing!.favourites.value : null),
		loaded: ref(seeded),
		pending: null,
		resets: {},
		timer: null,
		queue: Promise.resolve(),
		stale: false,
		refreshing: ref(seeded),
		refreshed: Promise.resolve(),
	};
	entries.set(doctype, entry);
	if (existing) {
		entry.queue = existing.queue.then(() => {
			carryPending(existing, entry);
			return load(entry, doctype);
		});
	} else load(entry, doctype);
	if (seeded) entry.refreshed = entry.queue;
	return entry;
}

function flushEntry(entry: Entry, doctype: string): Promise<void> {
	const patch = entry.pending;
	entry.pending = null;
	if (entry.timer) clearTimeout(entry.timer);
	entry.timer = null;
	if (!patch) return entry.queue;
	const marks = { ...entry.resets };
	const body = { doctype, type: VIEW_TYPE, scope: "user", settings: patch };
	return write(entry, () => send(`${API}.save`, body), () => restore(entry, patch, marks));
}

async function load(entry: Entry, doctype: string) {
	try {
		const response = await send(`${API}.get`, { doctype, type: VIEW_TYPE });
		const tiers = tiersOf(response);
		entry.favourites.value = favouritesOf(response);
		if (!entry.refreshing.value) entry.tiers.value = tiers;
		else
			landFresh(() => {
				// A write that landed while this read was held carries newer rows.
				if (!entry.refreshing.value) return;
				entry.tiers.value = tiers;
				entry.refreshing.value = false;
			});
	} catch (failure) {
		console.warn(`[list] settings for ${doctype} did not load`, failure);
		// A failed read keeps what is on show, and the next caller reads again.
		entry.stale = true;
		entry.refreshing.value = false;
	}
	entry.loaded.value = true;
}

function write(entry: Entry, send: () => Promise<unknown>, onFailure?: () => void): Promise<void> {
	entry.queue = entry.queue.then(async () => {
		try {
			entry.tiers.value = tiersOf(await send());
			entry.refreshing.value = false;
		} catch (failure) {
			onFailure?.();
			console.warn("[list] settings were not saved", failure);
		}
	});
	return entry.queue;
}

/** Whether `view`, or the list itself when null, is starred. */
export function isFavourite(favourites: ListFavourites | null, view: string | null): boolean {
	if (!favourites) return false;
	return view === null ? favourites.list : favourites.views.includes(view);
}

function toggleFavourite(entry: Entry, doctype: string, view: string | null): Promise<void> {
	const turn = entry.queue.then(async () => {
		const adding = !isFavourite(entry.favourites.value, view);
		const target = { doctype: "DocType", name: doctype, ...(view === null ? {} : { view }) };
		await runMethod(TOGGLE_FAVOURITE, { ...target, add: adding }, { nullable: true });
		markFavourite(entry, view, adding);
	});
	entry.queue = turn.catch(() => undefined);
	return turn;
}

function markFavourite(entry: Entry, view: string | null, favourited: boolean) {
	const { list, views } = entry.favourites.value ?? { list: false, views: [] };
	if (view === null) entry.favourites.value = { list: favourited, views };
	else {
		const others = views.filter((name) => name !== view);
		entry.favourites.value = { list, views: favourited ? [...others, view] : others };
	}
}

/** A patch that failed waits for the next flush, under whatever was saved since, minus any key reset since. */
function restore(entry: Entry, patch: ListSettings, marks: Entry["resets"]) {
	const kept: ListSettings = {};
	for (const key of Object.keys(patch) as ListSettingsKey[]) {
		if ((entry.resets[key] ?? 0) === (marks[key] ?? 0)) Object.assign(kept, { [key]: patch[key] });
	}
	entry.pending = { ...kept, ...entry.pending };
}

/** A failed write lands in the stale entry, which may have no holder left to flush it. */
function carryPending(from: Entry, to: Entry) {
	if (!from.pending) return;
	restore(to, from.pending, {});
	from.pending = null;
}

async function send(method: string, args: Record<string, unknown>): Promise<unknown> {
	const { data } = await runMethod(method, args);
	return data;
}

function tiersOf(response: unknown): Tiers {
	const rows = (response ?? {}) as { site?: unknown; user?: unknown };
	return { site: settingsOf(rows.site), user: settingsOf(rows.user) };
}

function favouritesOf(response: unknown): ListFavourites {
	const favourites = (response as { favourites?: Partial<ListFavourites> } | null)?.favourites;
	const views = Array.isArray(favourites?.views) ? favourites.views : [];
	return { list: favourites?.list === true, views: views.filter((v) => typeof v === "string") };
}

function settingsOf(value: unknown): ListSettings | null {
	return typeof value === "object" && value && !Array.isArray(value) ? (value as ListSettings) : null;
}
