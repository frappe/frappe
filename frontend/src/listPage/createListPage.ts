// A doctype's list page on the page engine: the lists its list.js files edit, and the rows they read.
import type { Router } from "vue-router";
import { createPageEngine, type PageEngine } from "@/pageEngine";
import { Surface } from "@/pageEngine/surface";
import type { View } from "@/list/view";
import { listScriptsLoaded, listScriptsOf, loadListScripts } from "./scriptLoader";
import {
  ACTION_KEYS,
  COLUMN_KEYS,
  ROW_ACTION_KEYS,
  type ListPageAction,
  type ListPageApi,
  type ListPageColumn,
  type ListRow,
  type ListRowAction,
} from "./types";

export interface ListPageHost {
  view: View;
  router: Router;
  meta: () => Record<string, any> | null;
  perms: () => Record<string, any>;
  roles: () => string[];
  permissionsReady?: () => Promise<unknown>;
}

/** What the view's renderer holds: the rows it shows and how they load again. */
export interface ListRendererState {
  rows: () => readonly ListRow[];
  selection: () => readonly string[];
  reload: () => void;
}

export interface ListPageLists {
  controls: Surface<ListPageAction>;
  columns: Surface<ListPageColumn>;
  bulkActions: Surface<ListPageAction>;
  rowActions: Surface<ListRowAction>;
}

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
  const lists: ListPageLists = {
    controls: new Surface<ListPageAction>({ surface: "controls", keys: ACTION_KEYS }),
    columns: new Surface<ListPageColumn>({ surface: "columns", keys: COLUMN_KEYS }),
    bulkActions: new Surface<ListPageAction>({ surface: "bulkActions", keys: ACTION_KEYS }),
    rowActions: new Surface<ListRowAction>({ surface: "rowActions", keys: ROW_ACTION_KEYS }),
  };
  let renderer = DETACHED;

  const engine = createPageEngine({
    doctype,
    name: doctype,
    pageName: "list",
    lists,
    sources: () => listScriptsOf(doctype),
    extras: () => listMembers(),
    meta: host.meta,
    perms: host.perms,
    roles: host.roles,
    router: host.router,
    sourcesReady: () => loadListScripts(doctype),
    permissionsReady: host.permissionsReady,
    loaded: () => listScriptsLoaded(doctype),
  });
  const page = engine.page as unknown as ListPageApi;

  return {
    page,
    engine,
    lists,
    attach: (state) => void (renderer = state),
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
        return Object.freeze([...renderer.rows()]);
      },
      get selection() {
        return Object.freeze([...renderer.selection()]);
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
      reload: () => (engine.hasLeft() ? undefined : renderer.reload()),
    };
  }
}
