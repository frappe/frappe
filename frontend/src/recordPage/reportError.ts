// The third destination for a customization failure (ticket 19): console always,
// toast for script editors, and — from here — one Error Log row an admin can read
// without being in the room. Fire-and-forget in every direction: a failed report
// never toasts, never logs, never retries, because an error channel that can
// itself error is a loop.
import { call } from "frappe-ui";
import { HOST_SOURCE } from "./context";

const REPORT_METHOD =
  "frappe.desk.customization_error.report_customization_error";

const MESSAGE_LIMIT = 1000;
const STACK_LIMIT = 4000;

export type CustomizationTier = "page_script" | "extension" | "file_script";

// One report per (source, event) per page session. This is the layer that kills
// the replay storm before a request is made, and still yields one row per user
// per visit — "50 people hit this today" at a volume the log can hold.
const reported = new Set<string>();
// An error already filed where more was known about it — a tombstone hit names
// the removal and its replacement — must not be filed a second time by the
// handler catch that sees it on the way out.
const filed = new WeakSet<object>();

export interface CustomizationErrorContext {
  /** `page-script:<name>`, an app name, or `host` — the attribution already carried. */
  source: string;
  /** A handler key, or `load` for a failure to arrive at all. */
  event: string;
  /** Overrides the tier the source implies: the tier's own fetch has no script. */
  tier?: CustomizationTier;
  doctype?: string;
  record?: string;
  route?: string;
}

/** `host` is the app's own bundled code; everything else unprefixed is an app. */
export function tierOf(source: string): CustomizationTier {
  if (source.startsWith("page-script:")) return "page_script";
  return source === HOST_SOURCE ? "file_script" : "extension";
}

export function reportCustomizationError(
  error: unknown,
  context: CustomizationErrorContext,
) {
  if (typeof error === "object" && error !== null) {
    if (filed.has(error)) return;
    filed.add(error);
  }
  const key = `${context.source} ${context.event}`;
  if (reported.has(key)) return;
  reported.add(key);
  // Every call site is already inside a catch, so a throw from here would escape
  // as the failure of whatever it was reporting. `call` is guarded both ways:
  // synchronously, and for whatever it hands back.
  try {
    const sent = call(REPORT_METHOD, {
      source: context.source,
      tier: context.tier ?? tierOf(context.source),
      event: context.event,
      doctype: context.doctype ?? "",
      message: messageOf(error).slice(0, MESSAGE_LIMIT),
      stack: stackOf(error).slice(0, STACK_LIMIT),
      record: context.record ?? "",
      route: context.route ?? currentRoute(),
    });
    void Promise.resolve(sent).catch(() => {});
  } catch {
    // An error channel that can itself error is a loop.
  }
}

/** Cleared alongside `toasted`, so a new page session reports afresh. */
export function resetCustomizationErrorReports() {
  reported.clear();
}

function messageOf(error: unknown) {
  return error instanceof Error ? error.message : String(error);
}

function stackOf(error: unknown) {
  return error instanceof Error ? (error.stack ?? "") : "";
}

function currentRoute() {
  return typeof location === "undefined"
    ? ""
    : `${location.pathname}${location.hash}`;
}
