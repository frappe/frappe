// Keeps the record's `docinfo` live over its realtime room, and repairs it after a dropped connection.
import { watch, type Ref } from "vue";
import { useDebounceFn } from "@vueuse/core";
import { subscribeToDoc, type RealtimeSocket } from "@framework/ui/socket";

/** One `docinfo_update` event: a row of one bucket, added, replaced or removed. */
export interface DocinfoUpdate {
	doc: Record<string, any>;
	key: string;
	action?: "add" | "update" | "delete";
}

interface Target {
	doctype: string;
	docname: string;
}

interface Options<T extends object> {
	socket: RealtimeSocket | undefined;
	docinfo: Ref<T | null>;
	/** Re-reads the whole sidecar; it may reject. */
	reload: () => Promise<void>;
}

// A log row's delta does not carry the bucket derived from it (`assignments`, `attachments`).
const DERIVED_LOGS = new Set(["assignment_logs", "attachment_logs"]);
// The keys are the server's docinfo names (`shared` is the `shares` part), and the row published
// is not the part's row, so the delta only says "re-read".
const REREAD_ONLY = new Set(["shared", "tags", "favourites"]);

/**
 * Follows one record at a time: `follow` joins its room, `dispose` leaves it and stops listening.
 * Rejoining rooms after a reconnect is the socket's job (`shell/socket.ts`); this only repairs the rows.
 */
export function useLiveDocinfo<T extends object>({ socket, docinfo, reload }: Options<T>) {
	let target: Target | null = null;
	let leaveRoom = () => {};
	let listening = false;
	let missedDeltas = false;
	let deltaBeforeDocinfo = false;

	// A failed re-read keeps the last sidecar on screen; the next delta or reconnect tries again.
	function reloadQuietly(scheduledFor: Target | null = target) {
		if (scheduledFor !== target) return;
		reload().catch((error) => {
			if (import.meta.env.DEV) console.warn("[record-page] docinfo re-read failed", error);
		});
	}

	// Once for a burst of deltas: an assign of three people lands three logs.
	const reloadSoon = useDebounceFn(reloadQuietly, 200);

	// `getdoc` may have read before the write that the dropped delta announced.
	watch(
		docinfo,
		(value) => {
			if (!value || !deltaBeforeDocinfo) return;
			deltaBeforeDocinfo = false;
			reloadQuietly();
		},
		{ flush: "sync" }
	);

	function follow(doctype: string, docname: string) {
		release();
		if (!socket) return;
		target = { doctype, docname };
		leaveRoom = subscribeToDoc(socket, doctype, docname);
		listen();
	}

	function release() {
		leaveRoom();
		leaveRoom = () => {};
		target = null;
		deltaBeforeDocinfo = false;
	}

	function dispose() {
		release();
		if (!socket || !listening) return;
		socket.off("docinfo_update", onDocinfoUpdate);
		socket.off("disconnect", onDisconnect);
		socket.off("connect", onConnect);
		listening = false;
	}

	function listen() {
		if (!socket || listening) return;
		socket.on("docinfo_update", onDocinfoUpdate);
		socket.on("disconnect", onDisconnect);
		socket.on("connect", onConnect);
		listening = true;
	}

	function onDocinfoUpdate(...args: unknown[]) {
		const event = args[0] as DocinfoUpdate;
		if (!target || !isForRecord(event, target)) return;
		if (!docinfo.value) {
			deltaBeforeDocinfo = true;
			return;
		}
		if (!REREAD_ONLY.has(event.key)) docinfo.value = applyDocinfoUpdate(docinfo.value, event);
		if (DERIVED_LOGS.has(event.key) || REREAD_ONLY.has(event.key)) reloadSoon(target);
	}

	function onDisconnect() {
		missedDeltas = true;
	}

	function onConnect() {
		if (!missedDeltas) return;
		missedDeltas = false;
		if (target) reloadQuietly();
	}

	return { follow, release, dispose, reloadQuietly: () => reloadQuietly() };
}

/** Whether a delta belongs to the record on screen. */
export function isForRecord(event: DocinfoUpdate, { doctype, docname }: Target) {
	const { reference_doctype, reference_name } = event?.doc ?? {};
	return reference_doctype === doctype && reference_name === docname;
}

/** Splices one delta into the bucket it names; a bucket the page does not hold is never added. */
export function applyDocinfoUpdate<T extends object>(docinfo: T, event: DocinfoUpdate): T {
	const bucket = (docinfo as Record<string, any>)[event.key];
	if (!Array.isArray(bucket)) return docinfo;
	return { ...docinfo, [event.key]: splice(bucket, event) };
}

function splice(bucket: any[], { doc, action = "update" }: DocinfoUpdate) {
	const present = bucket.some((row) => row.name === doc.name);
	if (action === "add" && !present) return [...bucket, doc];
	if (!present) return bucket;
	if (action === "delete") return bucket.filter((row) => row.name !== doc.name);
	return bucket.map((row) => (row.name === doc.name ? doc : row));
}
