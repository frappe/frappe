// The quick actions every record gets from the framework, gated by the record's rights.
// Each is an ordinary item on `page.quickActions`, so a script hides or reorders it by name.
import type { QuickAction, RecordPageApi } from "@/recordPage";
import { routeFor } from "@/router/routeFor";

export function quickActionBuiltins(perms: Record<string, any>, tagged = false): QuickAction[] {
  const actions: QuickAction[] = [];
  if (perms.print) actions.push({ name: "print", label: "Print", icon: "lucide-printer", run: print });
  actions.push({ name: "copy_link", label: "Copy link", icon: "lucide-link", run: copyLink });
  if (perms.delete) actions.push({ name: "delete", label: "Delete", icon: "lucide-trash-2", run: remove });
  // Only while the record has no tag: a tagged record has the chips' own "+" instead.
  if (perms.write && !tagged) actions.push({ name: "tags", label: "Tags", icon: "lucide-tag", tagging: true });
  return actions;
}

// Desk v1's print view; the new shell has no print page of its own yet.
function print(page: RecordPageApi) {
  const query = new URLSearchParams({ doctype: page.doctype, name: page.docname });
  window.open(`/printview?${query}`, "_blank");
}

// No clipboard outside a secure context; a throw here would reload the record over an unsaved draft.
async function copyLink(page: RecordPageApi) {
  if (!navigator.clipboard) return page.toast.error("Copying needs a secure connection");
  await navigator.clipboard.writeText(window.location.href);
  page.toast.success("Link copied");
}

// The list route resolves before the call: a throw after a successful delete would reload
// the record that no longer exists.
async function remove(page: RecordPageApi) {
  const confirmed = await page.dialog.danger({
    title: "Delete this record?",
    message: `${page.docname} will be deleted.`,
  });
  if (!confirmed) return;
  const list = routeFor(page.doctype);
  await page.call("frappe.client.delete", { doctype: page.doctype, name: page.docname });
  page.toast.success("Deleted");
  await page.router.push(list);
}
