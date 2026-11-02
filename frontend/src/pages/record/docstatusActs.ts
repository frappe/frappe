// `header.submit` and `header.cancel`: when each shows, the confirm before it and the call it sends.
import { runDocumentMethod } from "@framework/ui/api";
import type { RealtimeSocket } from "@framework/ui/socket";
import { __ } from "@/i18n";
import { errorMessage, type HeaderItem, type RecordPageApi } from "@/recordPage";
import { stripTags } from "./saveResponse";

export type DocstatusAct = "submit" | "cancel";

const DRAFT = 0;
const SUBMITTED = 1;
const CANCELLED = 2;

/** The state the acts read; `workflow_state_field` is the active workflow's, which owns the transitions. */
export interface DocstatusState {
  meta: { is_submittable?: number; workflow_state_field?: string | null } | null;
  saved: Record<string, any>;
  dirty: boolean;
  /** The server runs both calls under the `write` right as well as `submit` or `cancel`. */
  canWrite: boolean;
}

export function docstatusItems(
  { meta, saved, dirty, canWrite }: DocstatusState,
  run: (act: DocstatusAct) => Promise<void>
): HeaderItem[] {
  if (!meta?.is_submittable || meta.workflow_state_field || !canWrite || dirty) return [];
  if (saved.docstatus === DRAFT)
    return [
      {
        name: "submit",
        label: __("Submit"),
        display: "button",
        right: "submit",
        props: { variant: "solid" },
        run: () => run("submit"),
      },
    ];
  if (saved.docstatus === SUBMITTED)
    return [
      {
        name: "cancel",
        label: __("Cancel"),
        icon: "lucide-ban",
        group: "danger",
        right: "cancel",
        run: () => run("cancel"),
      },
    ];
  return [];
}

export function confirmDocstatus(page: RecordPageApi, act: DocstatusAct, title: string): Promise<true | null> {
  if (act === "submit")
    return page.dialog.confirm({
      title: __("Submit {0}?", [title]),
      message: __("After this, only fields allowed after submit can change."),
      confirmLabel: __("Submit"),
    });
  return page.dialog.danger({
    title: __("Cancel {0}?", [title]),
    message: __("This can't be undone."),
    confirmLabel: __("Cancel record"),
    cancelLabel: __("Keep"),
  });
}

/** `queue` picks the Submission Queue's method, which acts directly when the scheduler is off. */
export async function sendDocstatus(
  doctype: string,
  name: string,
  act: DocstatusAct,
  queue = false
): Promise<Record<string, any>> {
  try {
    const { data } = await runDocumentMethod<Record<string, any>>(doctype, name, queue ? `queue_${act}` : act);
    return data;
  } catch (exception) {
    throw new Error(stripTags(errorMessage(exception)));
  }
}

/** A queued act answers with the record unmoved: the Submission Queue moves its docstatus later. */
export function isQueued(document: Record<string, any>, act: DocstatusAct): boolean {
  return document.docstatus !== (act === "submit" ? SUBMITTED : CANCELLED);
}

export function queuedMessage(act: DocstatusAct): string {
  return act === "submit"
    ? __("Queued for Submit. The record reloads when it is done.")
    : __("Queued for Cancel. The record reloads when it is done.");
}

/** Calls `onDone` at the record's next `doc_update`, which the queued job's save publishes; returns a stop. */
export function whenRecordUpdated(
  socket: RealtimeSocket | undefined,
  doctype: string,
  name: string,
  onDone: () => void
): () => void {
  if (!socket) return () => {};
  const listener = (...args: unknown[]) => {
    const event = args[0] as { doctype?: string; name?: string } | undefined;
    if (event?.doctype !== doctype || event.name !== name) return;
    stop();
    onDone();
  };
  const stop = () => socket.off("doc_update", listener);
  socket.on("doc_update", listener);
  return stop;
}
