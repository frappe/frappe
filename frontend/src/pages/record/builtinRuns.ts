// The runs of the built-in copy and delete rows, loaded on the first run.
import { deleteDocument } from "@framework/ui/api";
import { ActDeclined } from "@/acts/dispatcher";
import type { RecordPageApi } from "@/recordPage";
import { routeFor } from "@/router/routeFor";

// No clipboard outside a secure context; a throw here would reload the record over an unsaved draft.
export async function copyLink(page: RecordPageApi) {
  await copy(page, window.location.href, "Link copied");
}

export async function copyId(page: RecordPageApi) {
  await copy(page, page.docname, "ID copied");
}

async function copy(page: RecordPageApi, text: string, confirmation: string) {
  if (!navigator.clipboard) return page.toast.error("Copying needs a secure connection");
  await navigator.clipboard.writeText(text);
  page.toast.success(confirmation);
}

// The list route resolves before the call: a throw after a successful delete would reload
// the record that no longer exists.
export async function remove(page: RecordPageApi) {
  const confirmed = await page.dialog.danger({
    title: "Delete this record?",
    message: `${page.docname} will be deleted.`,
  });
  if (!confirmed) throw new ActDeclined("header.delete");
  const list = routeFor(page.doctype);
  await deleteDocument(page.doctype, page.docname);
  page.toast.success("Deleted");
  await page.router.push(list);
}
