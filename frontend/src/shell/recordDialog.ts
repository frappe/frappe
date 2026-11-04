// The one way to open a record in the dialog. `main.ts` registers the dialog; the shell keeps
// the open requests above any page. The router's guard calls this for an opted-in doctype.
import { markRaw, readonly, shallowRef, type Component } from "vue";

/** One open record dialog, as the registered dialog receives it. */
export interface RecordDialogRequest {
	id: number;
	doctype: string;
	name: string;
	/** The page it opened over; it closes when the route leaves this path. */
	path: string;
	/** Takes the request off the stack, after the dialog's leave transition. */
	dismiss: () => void;
}

const requests = shallowRef<RecordDialogRequest[]>([]);
let dialog: Component | null = null;
let nextId = 0;
let pending: { doctype: string; name: string } | null = null;

/** The open requests, oldest first. */
export const recordDialogRequests = readonly(requests);

/** The last record a dialog saved or deleted: a list of that doctype under it reloads its rows. */
export const recordDialogWrite = shallowRef<{ doctype: string } | null>(null);

export function announceRecordDialogWrite(doctype: string) {
	recordDialogWrite.value = { doctype };
}

/** `main.ts` registers the dialog before the router can resolve a record address. */
export function registerRecordDialog(component: Component) {
	dialog = markRaw(component);
}

export function recordDialog(): Component | null {
	return dialog;
}

export function openRecordDialog(doctype: string, name: string, path: string) {
	if (!dialog) throw new Error("openRecordDialog was called before the dialog was registered");
	if (requests.value.some((one) => one.doctype === doctype && one.name === name)) return;
	const id = nextId++;
	const dismiss = () => (requests.value = requests.value.filter((one) => one.id !== id));
	requests.value = [...requests.value, { id, doctype, name, path, dismiss }];
}

/** A direct load has no page under the dialog: the router shows the list first, then calls `flushPendingRecordDialog`. */
export function openRecordDialogAfterNavigation(doctype: string, name: string) {
	pending = { doctype, name };
}

export function flushPendingRecordDialog(path: string, failed = false) {
	if (!pending) return;
	const { doctype, name } = pending;
	pending = null;
	if (failed) return;
	openRecordDialog(doctype, name, path);
}

/** Every dialog that opened over another page leaves at once, as on a route change. */
export function closeRecordDialogs(path: string) {
	requests.value = requests.value.filter((request) => request.path === path);
}
