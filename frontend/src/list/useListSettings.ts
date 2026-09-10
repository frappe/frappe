// One doctype's stored list settings: the site row and the person's own, fetched once per session
// beside meta, and written back silently. A write's response replaces both rows.
import { call } from "frappe-ui";
import { computed, getCurrentScope, onScopeDispose, ref, type ComputedRef, type Ref } from "vue";
import type { ListSettings, ListSettingsKey } from "./storedSettings";

const API = "frappe.desk.doctype.doctype_view.api";
export const VIEW_TYPE = "List";
/** Column edits in the popover come in bursts; one write carries the burst. */
export const WRITE_DEBOUNCE_MS = 500;

export type Scope = "user" | "site";

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
}

interface Tiers {
	site: ListSettings | null;
	user: ListSettings | null;
}

interface Entry {
	tiers: Ref<Tiers>;
	loaded: Ref<boolean>;
	pending: ListSettings | null;
	timer: ReturnType<typeof setTimeout> | null;
	/** Writes go out one after another, so a late response cannot overwrite a later one. */
	queue: Promise<void>;
}

const entries = new Map<string, Entry>();

export function useListSettings(doctype: string): ListSettingsHandle {
	const entry = entryFor(doctype);
	const address = { doctype, type: VIEW_TYPE };

	function flush(): Promise<void> {
		const patch = entry.pending;
		entry.pending = null;
		if (entry.timer) clearTimeout(entry.timer);
		entry.timer = null;
		if (!patch) return entry.queue;
		return write(entry, () => call(`${API}.save`, { ...address, scope: "user", settings: patch }));
	}

	function save(patch: ListSettings) {
		entry.pending = { ...entry.pending, ...patch };
		if (entry.timer) clearTimeout(entry.timer);
		entry.timer = setTimeout(flush, WRITE_DEBOUNCE_MS);
	}

	async function reset(key: ListSettingsKey) {
		if (entry.pending) delete entry.pending[key];
		await flush();
		await write(entry, () => call(`${API}.reset`, { ...address, scope: "user", key }));
	}

	async function saveForSite(patch: ListSettings) {
		await write(entry, () => call(`${API}.save`, { ...address, scope: "site", settings: patch }));
	}

	async function resetForSite(key: ListSettingsKey) {
		await write(entry, () => call(`${API}.reset`, { ...address, scope: "site", key }));
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
	};
}

/** Drops every fetched row, so one test's settings cannot reach the next. */
export function resetListSettings(): void {
	for (const entry of entries.values()) if (entry.timer) clearTimeout(entry.timer);
	entries.clear();
}

function entryFor(doctype: string): Entry {
	const existing = entries.get(doctype);
	if (existing) return existing;
	const entry: Entry = {
		tiers: ref({ site: null, user: null }),
		loaded: ref(false),
		pending: null,
		timer: null,
		queue: Promise.resolve(),
	};
	entries.set(doctype, entry);
	load(entry, doctype);
	return entry;
}

async function load(entry: Entry, doctype: string) {
	try {
		entry.tiers.value = tiersOf(await call(`${API}.get`, { doctype, type: VIEW_TYPE }));
	} catch (failure) {
		console.warn(`[list] settings for ${doctype} did not load`, failure);
	}
	entry.loaded.value = true;
}

function write(entry: Entry, send: () => Promise<unknown>): Promise<void> {
	entry.queue = entry.queue.then(async () => {
		try {
			entry.tiers.value = tiersOf(await send());
		} catch (failure) {
			console.warn("[list] settings were not saved", failure);
		}
	});
	return entry.queue;
}

function tiersOf(response: unknown): Tiers {
	const rows = (response ?? {}) as { site?: unknown; user?: unknown };
	return { site: settingsOf(rows.site), user: settingsOf(rows.user) };
}

function settingsOf(value: unknown): ListSettings | null {
	return typeof value === "object" && value && !Array.isArray(value) ? (value as ListSettings) : null;
}
