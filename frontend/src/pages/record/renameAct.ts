// `header.rename`, the `⋯` menu's "Rename…", and the `page.rename` it runs.
import { toast } from "frappe-ui";
import { renameDocument } from "@framework/ui/api";
import { __ } from "@/i18n";
import { errorMessage, type HeaderItem, type RecordPageApi } from "@/recordPage";
import { routeFor } from "@/router/routeFor";
import { runSave } from "./recordSave";
import { stripTags } from "./saveResponse";

export function renameItem(): HeaderItem {
  return {
    name: "rename",
    label: __("Rename…"),
    icon: "lucide-pencil",
    group: "assign_band",
    right: "write",
    run: openRename,
  };
}

/** Saves a dirty draft, then renames and replaces the address while `onRecord` holds; `null` when refused. */
export async function renameRecord(
  page: RecordPageApi,
  name: string,
  merge: boolean,
  onRecord: () => boolean
): Promise<string | null> {
  if (!(await runSave(page)) || !onRecord()) return null;
  let renamed: string;
  try {
    ({ data: renamed } = await renameDocument(page.doctype, page.docname, name, { merge }));
  } catch (exception) {
    toast.error(stripTags(errorMessage(exception)));
    return null;
  }
  if (!onRecord()) return renamed;
  // The old name is gone, so a reader who keeps edits made meanwhile is told where the record went.
  const refused = await page.router.replace(routeFor(page.doctype, renamed));
  if (refused) toast.error(__("Renamed to {0}; this page still shows the old name", [renamed]));
  else toast.success(__("Renamed"));
  return renamed;
}

async function openRename(page: RecordPageApi) {
  const values = await page.dialog.form({
    title: __("Rename {0}", [page.docname]),
    fields: [
      { fieldname: "new_name", fieldtype: "Data", label: newNameLabel(page.meta), reqd: 1 },
      { fieldname: "merge", fieldtype: "Check", label: __("Merge with existing") },
    ],
    defaults: { new_name: page.docname },
    submitLabel: __("Rename"),
  });
  if (!values) return;
  const name = String(values.new_name ?? "").trim();
  if (!name || name === page.docname) return;
  if (values.merge && !(await confirmMerge(page, name))) return;
  await page.rename(name, { merge: Boolean(values.merge) });
}

function newNameLabel(meta: Record<string, any> | null): string {
  const autoname = String(meta?.autoname ?? "");
  if (!autoname.startsWith("field:")) return __("New Name");
  const fieldname = autoname.slice("field:".length);
  const field = meta?.fields?.find((candidate: any) => candidate.fieldname === fieldname);
  return field?.label ? __("New {0}", [__(field.label)]) : __("New Name");
}

function confirmMerge(page: RecordPageApi, name: string) {
  return page.dialog.danger({
    title: __("Merge into {0}?", [name]),
    message: __("{0} will be merged into {1}. This cannot be undone.", [page.docname, name]),
    confirmLabel: __("Merge"),
  });
}
