// The list page's act surface, `list`: its built-ins as named acts, which its buttons and menu draw.
// A renderer's acts join as `<type>.<act>`, so List's own land on `list` too.
import { toast } from "frappe-ui";
import { onScopeDispose, shallowRef } from "vue";
import { acts, type ActEntry, type AvailableAct } from "@/acts/dispatcher";
import { __ } from "@/i18n";
import type { ListPageController, ListRendererState } from "@/listPage/createListPage";
import type { ListPermissions } from "@/listPage/listPermissions";
import type { ListPageApi } from "@/listPage/types";
import { favouriteWording } from "@/pages/favourite/favouriteWording";
import type { DefaultScope } from "./defaultView";
import { errorMessage } from "@/recordPage/errorMessage";
import { typeKey } from "@/list/view";

export interface ListActsHost {
  /** The list page: the acts' context, and its `controls` items that have `run`. */
  list: ListPageController;
  permissions: ListPermissions;
  create: () => unknown;
  customizeQuickFilter: () => void;
  customizing: () => boolean;
  /** False until a list settings read says what is starred. */
  starsLoaded: () => boolean;
  favourited: () => boolean;
  toggleFavourite: () => unknown;
  /** Opens the doctype's saved view `key`. */
  openView: (key: string) => unknown;
  /** Points one layer's default at the view `key`, a view type's name for its plain view. */
  setDefaultView: (key: string, scope: DefaultScope) => unknown;
  clearDefaultView: (scope: DefaultScope) => unknown;
}

export interface ListActs {
  /** The list page, which every act's `run` gets. */
  context: () => ListPageApi;
  /** The act by its item name while the dispatcher would run it, so the page draws it. */
  drawn: (name: string) => AvailableAct | undefined;
  perform: (act: AvailableAct, value?: unknown) => void;
}

export interface PageActs extends ListActs {
  /** Puts a renderer's acts on its type's surface, under the page's rights; they draw from the result. `state` is what the page reads its rows from. */
  renderer: (entries: () => ActEntry[], state: ListRendererState) => ListActs;
}

/** Registers the `list` surface for the page's life; the page draws its controls from `drawn`. */
export function useListActs(host: ListActsHost, type = "List"): PageActs {
  const { list, permissions } = host;
  const surface = typeKey(type);
  const rendered = shallowRef<() => ActEntry[]>(() => []);
  const pageEntries = () => [...listEntries(host), ...controlEntries(list)];
  const surfaces: Record<string, () => ActEntry[]> = { list: pageEntries };
  if (surface === "list") surfaces.list = () => [...pageEntries(), ...rendered.value()];
  else surfaces[surface] = () => rendered.value();
  const release = acts.register({
    surfaces,
    context: () => list.page,
    passes: permissions.passes,
    settled: () => (permissions.loading() ? permissions.ready() : undefined),
    hold: list.engine.hold,
    failed: (error) => void toast.error(errorMessage(error)),
  });
  onScopeDispose(release);

  return {
    ...surfaceActs("list"),
    renderer: (entries, state) => {
      rendered.value = entries;
      list.attach(state);
      return surfaceActs(surface);
    },
  };
}

function surfaceActs(surface: string): ListActs {
  return {
    context: () => acts.contextOf(surface) as ListPageApi,
    drawn: (name) => acts.find(`${surface}.${name}`),
    perform: (act, value) => void acts.perform(act.name, value),
  };
}

function listEntries(host: ListActsHost): ActEntry[] {
  return [
    {
      item: {
        name: "create",
        label: __("Create"),
        icon: "lucide-plus",
        right: "create",
        run: () => host.create(),
      },
      hidden: false,
    },
    {
      item: {
        name: "favourite",
        ...favouriteWording(host.favourited()),
        run: () => host.toggleFavourite(),
      },
      hidden: !host.starsLoaded(),
    },
    {
      item: {
        name: "open_view",
        label: __("Open View"),
        icon: "lucide-list",
        // The palette has no list of views to offer as options yet.
        palette: false,
        run: (_context: unknown, value?: { key?: unknown }) => host.openView(viewKey(value)),
      },
      hidden: false,
    },
    {
      item: {
        name: "set_default_view",
        label: __("Set Default View"),
        icon: "lucide-star",
        palette: false,
        run: (_context: unknown, value?: { key?: unknown; scope?: unknown }) =>
          host.setDefaultView(viewKey(value), defaultScope(value)),
      },
      hidden: false,
    },
    {
      item: {
        name: "clear_default_view",
        label: __("Clear Default View"),
        icon: "lucide-star-off",
        palette: false,
        run: (_context: unknown, value?: { scope?: unknown }) =>
          host.clearDefaultView(defaultScope(value)),
      },
      hidden: false,
    },
    {
      item: {
        name: "customize_quick_filter",
        label: __("Customize Quick Filter"),
        icon: "lucide-sliders-horizontal",
        run: () => host.customizeQuickFilter(),
      },
      hidden: host.customizing(),
    },
  ];
}

/** A script's `controls` item with `run` is an act; a built-in one draws itself. */
function controlEntries(list: ListPageController): ActEntry[] {
  return list.lists.controls
    .resolve()
    .filter(({ item }) => item.run)
    .map(({ item, hidden }) => ({ item, hidden }));
}

function viewKey(value?: { key?: unknown }): string {
  if (typeof value?.key !== "string" || !value.key)
    throw new Error(__("Name the view to open by its key."));
  return value.key;
}

function defaultScope(value?: { scope?: unknown }): DefaultScope {
  if (value?.scope !== "user" && value?.scope !== "site")
    throw new Error(__("Name the default's layer: user or site."));
  return value.scope;
}
