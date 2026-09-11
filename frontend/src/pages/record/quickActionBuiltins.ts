// The quick actions every record gets from the framework, gated by the record's rights.
// Each is an ordinary item on `page.quickActions`, so a script hides or reorders it by name.
import type { QuickAction, RecordPageApi } from "@/recordPage";
import { routeFor } from "@/router/routeFor";

export function quickActionBuiltins(perms: Record<string, any>): QuickAction[] {
  const actions: QuickAction[] = [];
  if (perms.print) actions.push({ name: "print", label: "Print", icon: "lucide-printer", run: print });
  actions.push({ name: "copy_link", label: "Copy link", icon: "lucide-link", run: copyLink });
  if (perms.delete) actions.push({ name: "delete", label: "Delete", icon: "lucide-trash-2", run: remove });
  return actions;
}

// Desk v1's print view; the new shell has no print page of its own yet.
function print(page: RecordPageApi) {
  const query = new URLSearchParams({ doctype: page.doctype, name: page.docname });
  window.open(`/printview?${query}`, "_blank");
}

async function copyLink(page: RecordPageApi) {
  await navigator.clipboard.writeText(window.location.href);
  page.toast.success("Link copied");
}

// Leaves for the list before anything could reload the record it just deleted.
async function remove(page: RecordPageApi) {
  const confirmed = await page.dialog.danger({
    title: "Delete this record?",
    message: `${page.docname} will be deleted.`,
  });
  if (!confirmed) return;
  await page.call("frappe.client.delete", { doctype: page.doctype, name: page.docname });
  page.toast.success("Deleted");
  await page.router.push(routeFor(page.doctype));
}
