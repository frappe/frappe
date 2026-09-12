// The actions every record gets from the framework, gated by its rights: quick actions on
// the panel, the `⋯` menu's rows in the header. Each is an ordinary item a script hides or reorders by name.
import type { HeaderItem, QuickAction, RecordPageApi } from "@/recordPage";
import { routeFor } from "@/router/routeFor";

export function quickActionBuiltins(perms: Record<string, any>, tagged = false): QuickAction[] {
  const actions: QuickAction[] = [];
  if (perms.print) actions.push({ name: "print", label: "Print", icon: "lucide-printer", run: print });
  actions.push({ name: "copy_link", label: "Copy link", icon: "lucide-link", run: copyLink });
  // Only while the record has no tag: a tagged record has the chips' own "+" instead.
  if (perms.write && !tagged) actions.push({ name: "tags", label: "Tags", icon: "lucide-tag", tagging: true });
  return actions;
}

/** The star's state and action, so the menu row can say the opposite and do the same. */
export interface FavouriteState {
  favourited: boolean;
  toggle: (page: RecordPageApi) => any;
}

/**
 * The header's `⋯` rows: no `display`, so the projection files them under the menu.
 * Three bands by `group`: the favourite, the record's copies, then Delete.
 */
export function headerMenuBuiltins(perms: Record<string, any>, favourite: FavouriteState): HeaderItem[] {
  const items: HeaderItem[] = [
    {
      name: "favourite_row",
      group: "favourite_band",
      run: favourite.toggle,
      ...(favourite.favourited
        ? { label: "Remove from favourites", icon: "lucide-star-off" }
        : { label: "Add to favourites", icon: "lucide-star" }),
    },
    { name: "copy_url", label: "Copy record URL", icon: "lucide-link", group: "copies", run: copyLink },
    { name: "copy_id", label: "Copy record ID", icon: "lucide-hash", group: "copies", run: copyId },
  ];
  if (perms.delete) items.push({ name: "delete", label: "Delete", icon: "lucide-trash-2", group: "danger", run: remove });
  return items;
}

// Desk v1's print view; the new shell has no print page of its own yet.
function print(page: RecordPageApi) {
  const query = new URLSearchParams({ doctype: page.doctype, name: page.docname });
  window.open(`/printview?${query}`, "_blank");
}

// No clipboard outside a secure context; a throw here would reload the record over an unsaved draft.
async function copyLink(page: RecordPageApi) {
  await copy(page, window.location.href, "Link copied");
}

async function copyId(page: RecordPageApi) {
  await copy(page, page.docname, "ID copied");
}

async function copy(page: RecordPageApi, text: string, confirmation: string) {
  if (!navigator.clipboard) return page.toast.error("Copying needs a secure connection");
  await navigator.clipboard.writeText(text);
  page.toast.success(confirmation);
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
