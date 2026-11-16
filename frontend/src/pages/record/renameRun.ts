// The Rename dialog's run, loaded on the first Rename so a record page's first paint does not carry it.
import { ActDeclined } from "@/acts/dispatcher";
import { __ } from "@/i18n";
import type { RecordPageApi } from "@/recordPage";

export async function openRename(page: RecordPageApi) {
  const values = await page.dialog.form({
    title: __("Rename {0}", [page.docname]),
    fields: [
      { fieldname: "new_name", fieldtype: "Data", label: newNameLabel(page.meta), reqd: 1 },
      { fieldname: "merge", fieldtype: "Check", label: __("Merge with existing") },
    ],
    defaults: { new_name: page.docname },
    submitLabel: __("Rename"),
  });
  if (!values) throw new ActDeclined("header.rename");
  const name = String(values.new_name ?? "").trim();
  if (!name || name === page.docname) return;
  if (values.merge && !(await confirmMerge(page, name))) throw new ActDeclined("header.rename");
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
