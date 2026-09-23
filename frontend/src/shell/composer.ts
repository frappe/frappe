// The one composer across records: the record and writer it is open on, and every draft of the session.
import { markRaw, reactive, readonly, shallowReactive } from "vue";
import { currentSession } from "@framework/ui/composables/useSession";
import type { UploadTransport } from "@framework/ui/FileUpload";
import type { ComposerWindow, RecordPageApi } from "@/recordPage";
import type { WriterItem } from "@/recordPage/types";

export type { ComposerWindow };
/** A writer's unsent state; the comment writer keeps `{ content, attachments }`. */
export type ComposerDraft = Record<string, unknown>;

/** What a writer needs from its record; the record page registers one while it is mounted. */
export interface WriterContext {
	doctype: string;
	docname: string;
	title: string;
	perms: Record<string, any>;
	/** The live record page's `page`, for a scripted writer's component; absent away from the record. */
	page?: RecordPageApi;
	toast: { error(message: string): void; success?(message: string): void };
	/** The record page's writers, a script's among them; absent away from the record. */
	writers?: WriterItem[];
	/** Fires the record page's `onPost`; absent away from the record. */
	firePost?(key: string): Promise<void>;
	/** The record page's upload transport; away from the record the writer builds a plain one. */
	uploadTransport?(): UploadTransport;
}

/** A record's title, permissions and plain writers as its page last showed them. */
export type KeptRecord = Pick<WriterContext, "title" | "perms" | "writers">;

const state = reactive({
	doctype: "",
	name: "",
	active: "",
	window: "docked" as ComposerWindow,
});
const drafts = reactive(new Map<string, ComposerDraft>());
const revisions = reactive(new Map<string, number>());
const docks = shallowReactive(new Map<string, HTMLElement>());
const records = shallowReactive(new Map<string, WriterContext>());
const kept = shallowReactive(new Map<string, KeptRecord>());

export const composerState = readonly(state);

/** Opens this record's writer; a draft in memory wins over `seed`, `placement` over the choice. */
export function openComposer(
	doctype: string,
	name: string,
	writer: string,
	seed?: ComposerDraft,
	placement?: ComposerWindow
) {
	const key = draftKey(doctype, name, writer);
	if (seed && !drafts.has(key)) drafts.set(key, { ...seed });
	const context = composerRecordFor(doctype, name);
	if (context) keep(doctype, name, context);
	const left = { doctype: state.doctype, name: state.name };
	Object.assign(state, { doctype, name, active: writer, window: placement ?? preferredWindow() });
	if (left.doctype !== doctype || left.name !== name) forget(left.doctype, left.name);
}

/** Keeps a record's title, permissions and writers from a context its writer still holds. */
export function keepComposerRecord(context: WriterContext) {
	keep(context.doctype, context.docname, context);
}

/** Collapses the band; the record's drafts stay. */
export function closeComposer() {
	state.active = "";
}

/** The writer open on this record, or `""` while the store is on another. */
export function activeWriter(doctype: string, name: string): string {
	return state.doctype === doctype && state.name === name ? state.active : "";
}

/** The store's record as its page last showed it, for the window away from it; the docname before. */
export function composerKept(): KeptRecord {
	return kept.get(recordKey(state.doctype, state.name)) ?? { title: state.name, perms: {} };
}

/** The reader the composer's stored choices belong to. */
export function composerUser(): string {
	return currentSession()?.user.name ?? "";
}

/** The reader's own choice of window, read from storage per user; an `open` never changes it. */
export function preferredWindow(user = composerUser()): ComposerWindow {
	try {
		return localStorage.getItem(windowStorageKey(user)) === "floating" ? "floating" : "docked";
	} catch {
		return "docked";
	}
}

/** Moves the open card; `remember` also keeps the choice for the next open. */
export function setComposerWindow(
	placement: ComposerWindow,
	{ remember = false }: { remember?: boolean } = {}
) {
	state.window = placement;
	if (!remember) return;
	try {
		localStorage.setItem(windowStorageKey(composerUser()), placement);
	} catch {
		// Storage can be full or refused; the next open then takes the default.
	}
}

/** The record's band offers `el` for the docked card; the returned function takes it back. */
export function registerComposerDock(doctype: string, name: string, el: HTMLElement) {
	return register(docks, recordKey(doctype, name), markRaw(el));
}

/** Where the docked card draws: the band of the record the store is on, or null. */
export function composerDock(): HTMLElement | null {
	return docks.get(recordKey(state.doctype, state.name)) ?? null;
}

/** The record page's context for its writers, while that page is mounted. */
export function registerComposerRecord(doctype: string, name: string, context: WriterContext) {
	keep(doctype, name, context);
	const unregister = register(records, recordKey(doctype, name), markRaw(context));
	return () => {
		// The page's last title and permissions stay for a window that outlives it.
		if (composerRecordFor(doctype, name) === context) keep(doctype, name, context);
		unregister();
		forget(doctype, name);
	};
}

/** The context of the record the store is on, or null away from that record. */
export function composerRecord(): WriterContext | null {
	return composerRecordFor(state.doctype, state.name);
}

/** The context of this record's page while it is mounted, or null. */
export function composerRecordFor(doctype: string, name: string): WriterContext | null {
	return records.get(recordKey(doctype, name)) ?? null;
}

export function composerDraft(
	doctype: string,
	name: string,
	writer: string
): ComposerDraft | undefined {
	return drafts.get(draftKey(doctype, name, writer));
}

export function saveComposerDraft(
	doctype: string,
	name: string,
	writer: string,
	draft: ComposerDraft
) {
	drafts.set(draftKey(doctype, name, writer), draft);
}

/** Sets a draft from outside its writer; a writer keyed on `draftRevision` redraws with it. */
export function replaceComposerDraft(
	doctype: string,
	name: string,
	writer: string,
	draft: ComposerDraft
) {
	const key = draftKey(doctype, name, writer);
	drafts.set(key, draft);
	revisions.set(key, (revisions.get(key) ?? 0) + 1);
}

export function draftRevision(doctype: string, name: string, writer: string): number {
	return revisions.get(draftKey(doctype, name, writer)) ?? 0;
}

export function clearComposerDraft(doctype: string, name: string, writer: string) {
	drafts.delete(draftKey(doctype, name, writer));
	forget(doctype, name);
}

// A page that mounts again registers before the old one unmounts; the old one must not take it back.
function register<T>(map: Map<string, T>, key: string, value: T) {
	map.set(key, value);
	return () => {
		if (map.get(key) === value) map.delete(key);
	};
}

// A script's writer takes `page`, so only the plain ones are kept for the window away from it.
function keep(doctype: string, name: string, context: WriterContext) {
	const writers = context.writers
		?.filter((item) => !item.component)
		.map((item) => ({ name: item.name, label: item.label, icon: item.icon }));
	const { title, perms } = context;
	kept.set(recordKey(doctype, name), { title: title || name, perms, writers });
}

// Kept only while a window may still need it: the store is on the record, or a draft waits there.
function forget(doctype: string, name: string) {
	const key = recordKey(doctype, name);
	if (records.has(key) || (state.doctype === doctype && state.name === name)) return;
	const prefix = `${key.slice(0, -1)},`;
	if (![...drafts.keys()].some((draft) => draft.startsWith(prefix))) kept.delete(key);
}

function windowStorageKey(user: string) {
	return `desk:composer-window:${user}`;
}

function recordKey(doctype: string, name: string) {
	return JSON.stringify([doctype, name]);
}

function draftKey(doctype: string, name: string, writer: string) {
	return JSON.stringify([doctype, name, writer]);
}
