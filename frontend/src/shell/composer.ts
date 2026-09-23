// The one composer across records: the record and writer it is open on, and every draft of the session.
import { reactive, readonly } from "vue";

export type ComposerWindow = "docked" | "floating";
/** A writer's unsent state; the comment writer keeps `{ content, attachments }`. */
export type ComposerDraft = Record<string, unknown>;

const state = reactive({
	doctype: "",
	name: "",
	active: "",
	window: "docked" as ComposerWindow,
});
const drafts = reactive(new Map<string, ComposerDraft>());
const revisions = reactive(new Map<string, number>());

export const composerState = readonly(state);

/** Takes the store for this record's writer; a draft already in memory wins over `seed`. */
export function openComposer(doctype: string, name: string, writer: string, seed?: ComposerDraft) {
	const key = draftKey(doctype, name, writer);
	if (seed && !drafts.has(key)) drafts.set(key, { ...seed });
	Object.assign(state, { doctype, name, active: writer, window: "docked" });
}

/** Collapses the band; the record's drafts stay. */
export function closeComposer() {
	state.active = "";
}

/** The writer open on this record, or `""` while the store is on another. */
export function activeWriter(doctype: string, name: string): string {
	return state.doctype === doctype && state.name === name ? state.active : "";
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

function draftKey(doctype: string, name: string, writer: string) {
	return JSON.stringify([doctype, name, writer]);
}
