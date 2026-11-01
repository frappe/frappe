// `header.submit` and `header.cancel`: when each shows, the confirm before it and the call it sends.
import { runDocumentMethod } from "@framework/ui/api";
import { __ } from "@/i18n";
import { errorMessage, type HeaderItem, type RecordPageApi } from "@/recordPage";
import { stripTags } from "./saveResponse";

export type DocstatusAct = "submit" | "cancel";

const DRAFT = 0;
const SUBMITTED = 1;

/** The state the acts read; `workflow_state_field` is the active workflow's, which owns the transitions. */
export interface DocstatusState {
  meta: { is_submittable?: number; workflow_state_field?: string | null } | null;
  saved: Record<string, any>;
  dirty: boolean;
}

export function docstatusItems(
  { meta, saved, dirty }: DocstatusState,
  run: (act: DocstatusAct) => Promise<void>
): HeaderItem[] {
  if (!meta?.is_submittable || meta.workflow_state_field) return [];
  if (saved.docstatus === DRAFT && !dirty)
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

export async function sendDocstatus(
  doctype: string,
  name: string,
  act: DocstatusAct
): Promise<Record<string, any>> {
  try {
    const { data } = await runDocumentMethod<Record<string, any>>(doctype, name, act);
    return data;
  } catch (exception) {
    throw new Error(stripTags(errorMessage(exception)));
  }
}
