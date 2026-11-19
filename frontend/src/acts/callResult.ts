// What `call` tells an outside caller: the act's data, or why it did not finish and what to do next.
import { ActDeclined, ActDenied, ActInvalid, type ActDeniedReason, type ActDialog, type ActError, type ActResult } from "./dispatcher";

const NEXT: Record<ActDeniedReason, string> = {
	missing: "List the acts that can run now and pick one of them.",
	hidden: "List the acts that can run now; this page does not offer it at this moment.",
	right: "The person's role does not allow it. Tell the person; do not try again.",
};

function errorOf(error: unknown, name: string): ActError {
	if (error instanceof ActDenied) return { code: error.reason, message: `${error.message}. ${error.detail ?? NEXT[error.reason]}` };
	if (error instanceof ActInvalid) return { code: "invalid", message: `${error.message}. Send a value that fits the act's input and run it again.` };
	if (error instanceof ActDeclined)
		return { code: "declined", message: `${name}: the person declined. Do not run it again unless the person asks for it.` };
	const reason = error instanceof Error && error.message ? error.message : String(error);
	return { code: "failed", message: `${reason.replace(/\.$/, "")}. Read the page state, fix the cause, then run the act again.` };
}

export async function callResult(run: Promise<unknown>, name: string, readDialogs: () => ActDialog[]): Promise<ActResult> {
	const where = () => ({ route: `${location.pathname}${location.search}${location.hash}`, dialogs: readDialogs() });
	try {
		const data = (await run) ?? null;
		return { ok: true, data, ...where() };
	} catch (error) {
		return { ok: false, error: errorOf(error, name), ...where() };
	}
}
