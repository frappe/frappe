// The runs of the saved-view acts on `list`: save, save as, discard, rename, delete and publish; loaded on first use.
import { runMethod } from "@framework/ui/api";
import type { Router } from "vue-router";
import { ActInvalid } from "@/acts/dispatcher";
import type { Boot } from "@/boot";
import { refreshSavedViews, type SavedView } from "@/list/savedView";
import type { ListPage } from "@/list/useListPage";
import { routeFor } from "@/router/routeFor";
import { skipDefaultOnce } from "@/router/skipDefault";

const API = "frappe.desk.doctype.doctype_view.api";

/** What the runs need of the open page. */
export interface ViewWriteHost {
  page: ListPage;
  boot: Boot;
  router: Router;
}

type Run = (host: ViewWriteHost, value: any) => Promise<unknown>;

/** Writes the page's filters, sort and columns to the open saved view, a shared one as a site administrator. */
async function saveView({ page }: ViewWriteHost) {
  const { view } = page;
  if (!view.layer)
    throw new ActInvalid("list.save_view", "this is a view type's plain view, which keeps its changes as you make them. Use list.save_view_as to keep them as a named view");
  if (!view.saveable.value)
    throw new ActInvalid("list.save_view", "only a site administrator can save a view everyone shares. Use list.save_view_as to keep the changes as your own view");
  const settings = page.snapshot();
  await write("save_view", { doctype: view.doctype, key: view.key, settings });
  page.commit(settings);
  refreshSavedViews();
  return { key: view.key };
}

/** A new view of the person's own from what the page shows, which they then open. */
async function saveViewAs({ page, router }: ViewWriteHost, { label }: { label: string }) {
  const { view } = page;
  const saved = await write<SavedView>("save_view_as", {
    doctype: view.doctype,
    label,
    settings: page.snapshot(),
    type: view.type,
  });
  refreshSavedViews();
  await router.push(routeFor(view.doctype, null, { view: saved.key }));
  return { key: saved.key, label: saved.label };
}

async function discardChanges({ page }: ViewWriteHost) {
  if (!page.view.layer)
    throw new ActInvalid("list.discard_changes", "this is a view type's plain view, which has no saved state to go back to");
  page.discard();
  return { key: page.view.key };
}

async function renameView({ page }: ViewWriteHost, { key, label }: { key: string; label: string }) {
  const saved = await write<SavedView>("rename_view", { doctype: page.view.doctype, key, label });
  refreshSavedViews();
  return { key: saved.key, label: saved.label };
}

/** Deletes the view; an app's view of the same key answers again when a site row over it goes. */
async function deleteView({ page, boot, router }: ViewWriteHost, { key }: { key: string }) {
  const { doctype } = page.view;
  const { restored } = await write<{ key: string; restored: boolean }>("delete_view", { doctype, key });
  if (!restored && boot.default_views?.[doctype] === key) delete boot.default_views[doctype];
  if (key === page.view.key && !restored) {
    // The open view is gone: the plain list opens, not the person's default in its place.
    skipDefaultOnce(doctype);
    await router.replace(routeFor(doctype));
  }
  refreshSavedViews();
  return { key, restored };
}

async function publishView({ page }: ViewWriteHost, { key }: { key: string }) {
  const saved = await write<SavedView>("publish_view", { doctype: page.view.doctype, key });
  refreshSavedViews();
  return { key: saved.key, layer: saved.layer };
}

async function write<Reply>(method: string, args: Record<string, unknown>): Promise<Reply> {
  const { data } = await runMethod<Reply>(`${API}.${method}`, args);
  return data;
}

/** The run of each act, by act name; the list's entries call them with the act's input. */
export const RUNS: Record<string, Run> = {
  save_view: saveView,
  save_view_as: saveViewAs,
  discard_changes: discardChanges,
  rename_view: renameView,
  delete_view: deleteView,
  publish_view: publishView,
};
