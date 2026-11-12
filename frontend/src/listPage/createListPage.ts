// A doctype's list page on the page engine: the lists its list.js files edit, and the rows they read.
import { shallowRef } from "vue";
import type { Router } from "vue-router";
import { createPageEngine, type PageEngine } from "@/pageEngine";
import { Surface } from "@/pageEngine/surface";
import { clientScriptWait, replacedClientScripts } from "@/recordPage/clientScripts";
import { LIST_PAGE_TIER } from "@/recordPage/clientScriptTypes";
import type { ListPermissions } from "./listPermissions";
import { listScriptsLoaded, listScriptsOf, loadListScripts } from "./scriptLoader";
import {
  ACTION_KEYS,
  COLUMN_KEYS,
  ROW_ACTION_KEYS,
  type ListPageAction,
  type ListPageApi,
  type ListPageColumn,
  type ListPageView,
  type ListRow,
  type ListRowAction,
} from "./types";

export interface ListPageHost {
  view: ListPageView;
  router: Router;
  meta: () => Record<string, any> | null;
  permissions: ListPermissions;
}

/** What the view's renderer holds: the rows it shows and how they load again. */
export interface ListRendererState {
  rows: () => readonly ListRow[];
  selection: () => readonly string[];
  reload: () => void;
}

export type ListPageLists = {
  controls: Surface<ListPageAction>;
  columns: Surface<ListPageColumn>;
  bulkActions: Surface<ListPageAction>;
  rowActions: Surface<ListRowAction>;
};

export interface ListPageController {
  page: ListPageApi;
  engine: PageEngine<ListPageLists, object>;
  lists: ListPageLists;
  /** The renderer hands in its rows; the page reads none until it does. */
  attach: (state: ListRendererState) => void;
  /** Paints at once when the scripts are in, else replays when they land. */
  paint: () => void;
  leave: () => void;
}

const DETACHED: ListRendererState = { rows: () => [], selection: () => [], reload: () => {} };

export function createListPage(host: ListPageHost): ListPageController {
  const { doctype } = host.view;
  const lists = createListPageLists();
  // A ref, so a computed that read `page.rows` before the renderer came reads them again.
  const renderer = shallowRef(DETACHED);
  const { permissions } = host;

  const engine = createPageEngine({
    doctype,
    name: doctype,
    pageName: "list",
    lists,
    sources: () => listScriptsOf(doctype),
    extras: () => listMembers(),
    meta: host.meta,
    perms: permissions.perms,
    roles: permissions.roles,
    router: host.router,
    sourcesReady: () => loadListScripts(doctype),
    permissionsReady: permissions.ready,
    loaded: () => listScriptsLoaded(doctype) && !permissions.loading(),
    skippedBeforeSources: () => replacedClientScripts(doctype, LIST_PAGE_TIER),
    lateLabel: () => clientScriptWait(doctype, LIST_PAGE_TIER) ?? "the list's scripts",
  });
  const page = engine.page as unknown as ListPageApi;

  return {
    page,
    engine,
    lists,
    attach: (state) => {
      renderer.value = state;
      // The renderer gives the built-in columns and bulk actions; replay so a script's `has` sees them.
      if (engine.ready.value) void engine.refresh();
    },
    paint: () => {
      if (!engine.paintNow()) void engine.refresh();
    },
    leave: () => engine.leave(),
  };

  function listMembers() {
    const { view } = host;
    return {
      view: { key: view.key, type: view.type },
      get rows() {
        return Object.freeze([...renderer.value.rows()]);
      },
      get selection() {
        return Object.freeze([...renderer.value.selection()]);
      },
      get filters() {
        return view.filters.value;
      },
      set filters(value) {
        view.filters.value = value;
      },
      get sort() {
        return view.sort.value;
      },
      set sort(value) {
        view.sort.value = value;
      },
      reload: () => (engine.hasLeft() ? undefined : renderer.value.reload()),
    };
  }
}

/** The list page's four lists, empty; a renderer's tests take them without a page. */
export function createListPageLists(): ListPageLists {
  return {
    controls: new Surface<ListPageAction>({ surface: "controls", keys: ACTION_KEYS }),
    columns: new Surface<ListPageColumn>({ surface: "columns", keys: COLUMN_KEYS }),
    bulkActions: new Surface<ListPageAction>({ surface: "bulkActions", keys: ACTION_KEYS }),
    rowActions: new Surface<ListRowAction>({ surface: "rowActions", keys: ROW_ACTION_KEYS }),
  };
}
