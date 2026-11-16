// What `call` tells an outside caller when an act did not finish: a code and the next step.
import { ActDeclined, ActDenied, ActInvalid, type ActDeniedReason, type ActError } from "./dispatcher";

const NEXT: Record<ActDeniedReason, string> = {
	missing: "List the acts that can run now and pick one of them.",
	hidden: "List the acts that can run now; this page does not offer it at this moment.",
	right: "The person's role does not allow it. Tell the person; do not try again.",
};

export function errorOf(error: unknown, name: string): ActError {
	if (error instanceof ActDenied) return { code: error.reason, message: `${error.message}. ${NEXT[error.reason]}` };
	if (error instanceof ActInvalid) return { code: "invalid", message: `${error.message}. Send a value that fits the act's input and run it again.` };
	if (error instanceof ActDeclined)
		return { code: "declined", message: `${name}: the person declined. Do not run it again unless the person asks for it.` };
	const reason = error instanceof Error && error.message ? error.message : String(error);
	return { code: "failed", message: `${reason.replace(/\.$/, "")}. Read the page state, fix the cause, then run the act again.` };
}
