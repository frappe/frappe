// The one composer across records: the record and writer it is open on, and every draft of the session.
import { markRaw, reactive, readonly, shallowReactive, shallowRef } from "vue";
import { currentSession } from "@framework/ui/composables/useSession";
import type { ComposerWindow, RecordPageApi } from "@/recordPage";

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
	/** Fires the record page's `onPost`; absent away from the record. */
	firePost?(key: string): Promise<void>;
	/** The record page's upload transport; away from the record the writer builds a plain one. */
	uploadTransport?(): unknown;
}

const state = reactive({
	doctype: "",
	name: "",
	active: "",
	window: "docked" as ComposerWindow,
	/** The record's title as it was at open, for the window away from its record. */
	title: "",
});
const keptPerms = shallowRef<Record<string, any>>({});
const drafts = reactive(new Map<string, ComposerDraft>());
const revisions = reactive(new Map<string, number>());
const remembered = reactive(new Map<string, ComposerWindow>());
const docks = shallowReactive(new Map<string, HTMLElement>());
const records = shallowReactive(new Map<string, WriterContext>());

export const composerState = readonly(state);

/**
 * Takes the store for this record's writer; a draft already in memory wins over `seed`.
 * `window` places the card for this open only; unset, the reader's remembered state does.
 */
export function openComposer(
	doctype: string,
	name: string,
	writer: string,
	seed?: ComposerDraft,
	window?: ComposerWindow
) {
	const key = draftKey(doctype, name, writer);
	if (seed && !drafts.has(key)) drafts.set(key, { ...seed });
	const context = records.get(recordKey(doctype, name));
	Object.assign(state, {
		doctype,
		name,
		active: writer,
		window: window ?? preferredWindow(),
		title: context?.title || name,
	});
	keptPerms.value = context?.perms ?? {};
}

/** Collapses the band; the record's drafts stay. */
export function closeComposer() {
	state.active = "";
}

/** The writer open on this record, or `""` while the store is on another. */
export function activeWriter(doctype: string, name: string): string {
	return state.doctype === doctype && state.name === name ? state.active : "";
}

/** The record's title as it was when the writer opened, or the docname. */
export function composerTitle(): string {
	return state.title;
}

/** The record's permissions as they were when the writer opened. */
export function composerPerms(): Record<string, any> {
	return keptPerms.value;
}

/** The reader's own choice of window, kept per user; an `open` option never changes it. */
export function preferredWindow(user = sessionUser()): ComposerWindow {
	return remembered.get(user) ?? storedWindow(user);
}

/** Moves the open card; `remember` also keeps the choice for the next open. */
export function setComposerWindow(
	window: ComposerWindow,
	{ remember = false }: { remember?: boolean } = {}
) {
	state.window = window;
	if (remember) rememberWindow(window);
}

/** Keeps the choice for the next open without moving a card that is open. */
export function rememberWindow(window: ComposerWindow, user = sessionUser()) {
	remembered.set(user, window);
	try {
		localStorage.setItem(windowStorageKey(user), window);
	} catch {
		// Storage can be full or refused; the choice still holds for the session.
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
	const key = recordKey(doctype, name);
	const unregister = register(records, key, markRaw(context));
	// An open that came before the page registered kept the docname; the title is known now.
	if (recordKey(state.doctype, state.name) === key) {
		state.title = context.title || name;
		keptPerms.value = context.perms;
	}
	return unregister;
}

/** The context of the record the store is on, or null away from that record. */
export function composerRecord(): WriterContext | null {
	return records.get(recordKey(state.doctype, state.name)) ?? null;
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
}

// A page that mounts again registers before the old one unmounts; the old one must not take it back.
function register<T>(map: Map<string, T>, key: string, value: T) {
	map.set(key, value);
	return () => {
		if (map.get(key) === value) map.delete(key);
	};
}

function storedWindow(user: string): ComposerWindow {
	try {
		return localStorage.getItem(windowStorageKey(user)) === "floating" ? "floating" : "docked";
	} catch {
		return "docked";
	}
}

function windowStorageKey(user: string) {
	return `desk:composer-window:${user}`;
}

function sessionUser() {
	return currentSession()?.user.name ?? "";
}

function recordKey(doctype: string, name: string) {
	return JSON.stringify([doctype, name]);
}

function draftKey(doctype: string, name: string, writer: string) {
	return JSON.stringify([doctype, name, writer]);
}
