// Where every script lands, whatever delivered it: file scripts at bundle
// evaluation, extensions as the loader imports them. Run order is precedence.
import { registeringSource } from "./context";
import { flattenHandlers } from "./flattenHandlers";
import type { AuthoredHandlers, RecordPageHandlers } from "./types";

export const ALL_DOCTYPES = "*";

export interface Registration {
  source: string;
  doctype: string;
  handlers: RecordPageHandlers;
}

const registrations: Registration[] = [];

export function registerRecordPage(
  doctype: string,
  handlers: AuthoredHandlers,
) {
  const source = registeringSource();
  // The one place a nested table block is flattened: file scripts and stored
  // scripts both land here, so neither the loader nor the evaluator has to know
  // the authored shape from the dispatched one.
  registrations.push({
    source,
    doctype,
    handlers: flattenHandlers(handlers, source, doctype),
  });
}

/** Sources in registration order; within one, `*` handlers before the doctype's own. */
export function registrationsFor(doctype: string): Registration[] {
  const bySource = new Map<string, Registration[]>();
  for (const registration of registrations) {
    if (
      registration.doctype !== doctype &&
      registration.doctype !== ALL_DOCTYPES
    )
      continue;
    const own = bySource.get(registration.source) ?? [];
    own.push(registration);
    bySource.set(registration.source, own);
  }
  return [...bySource.values()].flatMap((own) =>
    own.sort((a, b) => specificity(a) - specificity(b)),
  );
}

/** Drops a source's handlers, so a re-registered tier lands in creation order again. */
export function unregisterSource(source: string) {
  for (let index = registrations.length - 1; index >= 0; index--)
    if (registrations[index].source === source) registrations.splice(index, 1);
}

function specificity(registration: Registration) {
  return registration.doctype === ALL_DOCTYPES ? 0 : 1;
}

export function resetRegistry() {
  registrations.length = 0;
}
