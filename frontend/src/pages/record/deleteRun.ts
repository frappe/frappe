// The built-in Delete row's run, loaded on the first Delete.
import { deleteDocument } from "@framework/ui/api";
import { ActDeclined } from "@/acts/dispatcher";
import type { RecordPageApi } from "@/recordPage";
import { routeFor } from "@/router/routeFor";

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
