// Where every script lands, whatever delivered it: file scripts at bundle
// evaluation, extensions as the loader imports them. Run order is precedence.
import { registeringSource } from "./context";
import type { RecordPageHandlers } from "./types";

export const ALL_DOCTYPES = "*";

export interface Registration {
	source: string;
	doctype: string;
	handlers: RecordPageHandlers;
}

const registrations: Registration[] = [];

export function registerRecordPage(doctype: string, handlers: RecordPageHandlers) {
	registrations.push({ source: registeringSource(), doctype, handlers });
}

/** Sources in registration order; within one, `*` handlers before the doctype's own. */
export function registrationsFor(doctype: string): Registration[] {
	const bySource = new Map<string, Registration[]>();
	for (const registration of registrations) {
		if (registration.doctype !== doctype && registration.doctype !== ALL_DOCTYPES) continue;
		const own = bySource.get(registration.source) ?? [];
		own.push(registration);
		bySource.set(registration.source, own);
	}
	return [...bySource.values()].flatMap((own) =>
		own.sort((a, b) => specificity(a) - specificity(b)),
	);
}

function specificity(registration: Registration) {
	return registration.doctype === ALL_DOCTYPES ? 0 : 1;
}

export function resetRegistry() {
	registrations.length = 0;
}
