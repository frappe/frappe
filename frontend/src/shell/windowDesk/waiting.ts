// The two results `window.desk.acts` adds to `call`'s: an act that waits on a person, and a call id nobody holds.
import type { ActDialog, ActResult } from "@/acts/dispatcher";

const where = (readDialogs: () => ActDialog[]) => ({ route: `${location.pathname}${location.search}${location.hash}`, dialogs: readDialogs() });

/** An act that has not ended: a person must answer its dialog, or it still runs. */
export function waitingResult(call: number, dialog: ActDialog | undefined, readDialogs: () => ActDialog[]): ActResult {
	const message = dialog
		? `The person must answer "${dialog.title}". Do not answer it yourself. Call wait with this call id, or tell the person.`
		: "The act has not ended yet. Call wait with this call id again.";
	return { ok: false, error: { code: "waiting_for_user", message, dialog, call }, ...where(readDialogs) };
}

export function missingCall(call: number, readDialogs: () => ActDialog[]): ActResult {
	const message = `No call has the id ${call}. A call id comes from a run that returned waiting_for_user.`;
	return { ok: false, error: { code: "missing", message }, ...where(readDialogs) };
}
