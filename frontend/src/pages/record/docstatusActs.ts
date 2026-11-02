// `header.submit` and `header.cancel`: when each shows, the confirm before it and the call it sends.
import { getDocument, runDocumentMethod, runMethod } from "@framework/ui/api";
import { __ } from "@/i18n";
import { errorMessage, type HeaderItem, type RecordPageApi } from "@/recordPage";
import { stripTags } from "./saveResponse";

export type DocstatusAct = "submit" | "cancel";

const DRAFT = 0;
const SUBMITTED = 1;
const CANCELLED = 2;

const LINKED_DOCS = "frappe.desk.form.linked_with.get_submitted_linked_docs";
const CANCEL_ALL = "frappe.desk.form.linked_with.cancel_all_linked_docs";
const HAS_PERMISSION = "frappe.client.has_permission";
const NAMES_PER_DOCTYPE = 10;

export interface LinkedDoc {
  doctype: string;
  name: string;
  docstatus: number;
}

/** Cancel alone, or with the submitted records linked to it; `docs` is null past the server's listing cap. */
export type DocstatusChoice = { all: false } | { all: true; docs: LinkedDoc[] | null };

export interface DocstatusRecord {
  doctype: string;
  name: string;
  title: string;
}

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

export async function confirmDocstatus(
  page: RecordPageApi,
  act: DocstatusAct,
  record: DocstatusRecord
): Promise<DocstatusChoice | null> {
  const alone: DocstatusChoice = { all: false };
  if (act === "submit") {
    const confirmed = await page.dialog.confirm({
      title: __("Submit {0}?", [record.title]),
      message: __("After this, only fields allowed after submit can change."),
      confirmLabel: __("Submit"),
    });
    return confirmed ? alone : null;
  }
  const linked = await submittedLinks(record);
  if (!linked.truncated && !linked.docs.length) {
    const confirmed = await page.dialog.danger({
      title: __("Cancel {0}?", [record.title]),
      message: __("This can't be undone."),
      confirmLabel: __("Cancel record"),
      cancelLabel: __("Keep"),
    });
    return confirmed ? alone : null;
  }
  return confirmWithLinks(page, record, linked);
}

async function confirmWithLinks(
  page: RecordPageApi,
  record: DocstatusRecord,
  linked: { docs: LinkedDoc[]; truncated: boolean }
): Promise<DocstatusChoice | null> {
  const title = __("Cancel {0}?", [record.title]);
  if (linked.truncated) {
    const message = __(
      "{0} is linked with too many submitted records to list. Cancelling them all runs in the background, and you are told when it finishes.",
      [record.title]
    );
    return askCancelAll(page, { title, message }, { all: true, docs: null });
  }
  const message = __("{0} is linked with these submitted records: {1}.", [record.title, listByDoctype(linked.docs)]);
  if (await canCancelAll(linked.docs))
    return askCancelAll(page, { title, message }, { all: true, docs: linked.docs });
  const note = __("You do not have permission to cancel all of them.");
  await page.dialog.confirm({ title, message: `${message} ${note}`, actions: [{ label: __("Close") }] });
  return null;
}

async function askCancelAll(
  page: RecordPageApi,
  { title, message }: { title: string; message: string },
  choice: DocstatusChoice
) {
  const confirmed = await page.dialog.danger({
    title,
    message,
    confirmLabel: __("Cancel all"),
    cancelLabel: __("Keep"),
  });
  return confirmed ? choice : null;
}

/** `Payment Entry: PE-1, PE-2; Journal Entry: JV-1`, each DocType capped at ten names. */
function listByDoctype(docs: LinkedDoc[]): string {
  const byDoctype = new Map<string, string[]>();
  for (const { doctype, name } of docs) byDoctype.set(doctype, [...(byDoctype.get(doctype) ?? []), name]);
  return [...byDoctype]
    .map(([doctype, names]) => {
      const shown = names.slice(0, NAMES_PER_DOCTYPE).join(", ");
      const more = names.length > NAMES_PER_DOCTYPE ? __(", and {0} more", [String(names.length - NAMES_PER_DOCTYPE)]) : "";
      return `${__(doctype)}: ${shown}${more}`;
    })
    .join("; ");
}

/** The server cancels the lot in one transaction, so one refused DocType refuses all. */
async function canCancelAll(docs: LinkedDoc[]): Promise<boolean> {
  const oneOfEach = new Map(docs.map((doc) => [doc.doctype, doc.name]));
  const answers = await Promise.all(
    [...oneOfEach].map(([doctype, docname]) =>
      call<{ has_permission: boolean }>(HAS_PERMISSION, { doctype, docname, perm_type: "cancel" })
    )
  );
  return answers.every((answer) => answer.has_permission);
}

async function submittedLinks({ doctype, name }: DocstatusRecord) {
  return call<{ docs: LinkedDoc[]; truncated: boolean }>(LINKED_DOCS, { doctype, name });
}

/** `queue` picks the Submission Queue's method, which acts directly when the scheduler is off. `choice.all` cancels the linked records too; null comes back when they were handed to a background job. */
export async function sendDocstatus(
  doctype: string,
  name: string,
  act: DocstatusAct,
  queue = false,
  choice: DocstatusChoice = { all: false }
): Promise<Record<string, any> | null> {
  try {
    if (choice.all) return await cancelWithLinks(doctype, name, choice.docs);
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

async function cancelWithLinks(doctype: string, name: string, docs: LinkedDoc[] | null) {
  const args = { root_doctype: doctype, root_name: name, ...(docs && { docs }) };
  const { data } = await runMethod<{ queued?: boolean }>(CANCEL_ALL, args, { nullable: true });
  if (data?.queued) return null;
  return (await getDocument(doctype, name)).data;
}

async function call<T>(method: string, args: Record<string, unknown>): Promise<T> {
  try {
    return (await runMethod<T>(method, args)).data;
  } catch (exception) {
    throw new Error(stripTags(errorMessage(exception)));
  }
}
