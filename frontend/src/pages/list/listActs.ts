// The list page's act surface, `list`: its built-ins as named acts, which its buttons and menu draw.
// A renderer's acts join as `<type>.<act>`, so List's own land on `list` too.
import { toast } from "frappe-ui";
import { onScopeDispose, shallowRef } from "vue";
import { useDocPermissions } from "@framework/ui/useDocPermissions";
import { useSession } from "@framework/ui/useSession";
import {
  acts,
  type ActEntry,
  type ActRight,
  type AvailableAct,
} from "@/acts/dispatcher";
import type { ListContext } from "@/contributions/types";
import { useCreateRight } from "@/createRight";
import { __ } from "@/i18n";
import { whenLoaded } from "@/acts/doctypeRight";
import { favouriteWording } from "@/pages/favourite/favouriteWording";
import type { DefaultScope } from "./defaultView";
import { errorMessage } from "@/recordPage/errorMessage";
import { typeKey, type View } from "@/list/view";

export interface ListActsHost {
  doctype: string;
  view: View;
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

/** What the renderer holds of the list context: the rows it shows and how they load again. */
export type RendererContext = Pick<ListContext<View>, "selection" | "reload">;

export interface ListActs {
  /** The context an act's `run` gets now, without a row. */
  context: () => ListContext<View>;
  /** The act by its item name while the dispatcher would run it, so the page draws it. */
  drawn: (name: string) => AvailableAct | undefined;
  perform: (act: AvailableAct, value?: unknown) => void;
}

export interface PageActs extends ListActs {
  /** Puts a renderer's acts on its type's surface, under the page's rights; they draw from the result. `context` is its part of the list context. */
  renderer: (entries: () => ActEntry[], context: () => RendererContext) => ListActs;
}

/** Registers the `list` surface for the page's life; the page draws its controls from `drawn`. */
export function useListActs(host: ListActsHost, type = "List"): PageActs {
  const passes = useListRight(host.doctype);
  const { loading } = useDocPermissions(host.doctype);
  const surface = typeKey(type);
  const rendered = shallowRef<() => ActEntry[]>(() => []);
  const renderedContext = shallowRef<() => RendererContext>(() => ({ selection: [], reload: () => {} }));
  const surfaces: Record<string, () => ActEntry[]> = { list: () => listEntries(host) };
  if (surface === "list") surfaces.list = () => [...listEntries(host), ...rendered.value()];
  else surfaces[surface] = () => rendered.value();
  const release = acts.register({
    surfaces,
    context: () => ({
      doctype: host.doctype,
      view: host.view,
      ...renderedContext.value(),
      selection: [...renderedContext.value().selection],
    }),
    passes,
    settled: () => (loading.value ? whenLoaded(loading) : undefined),
    hold: async (work) => work(),
    failed: (error) => void toast.error(errorMessage(error)),
  });
  onScopeDispose(release);

  return {
    ...surfaceActs("list"),
    renderer: (entries, context) => {
      rendered.value = entries;
      renderedContext.value = context;
      return surfaceActs(surface);
    },
  };
}

function surfaceActs(surface: string): ListActs {
  return {
    context: () => acts.contextOf(surface) as ListContext<View>,
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

/** A right on the list's doctype; its create right is the list's Create rule. */
function useListRight(doctype: string): (right: ActRight) => boolean {
  const canCreate = useCreateRight(doctype);
  const { holds } = useDocPermissions(doctype);
  const { session } = useSession();
  return (right) => {
    if (typeof right !== "string") return false;
    if (right === "create") return canCreate.value;
    return session.value?.user.name === "Administrator" || holds(right);
  };
}
