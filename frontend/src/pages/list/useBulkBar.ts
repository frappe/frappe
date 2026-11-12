// The list's acts (bulk, row and keys) and the bulk bar. The bar's actions, layout and dialogs are a lazy chunk
// (`bulkBarParts`), so a list that is never selected does not load them.
import { toast } from "frappe-ui";
import { computed, effectScope, inject, ref, shallowRef, watch, type Component, type ComputedRef, type Ref, type ShallowRef } from "vue";
import type { ActEntry } from "@/acts/dispatcher";
import type { Boot } from "@/boot";
import { __ } from "@/i18n";
import type { ListRow, ListRowAction } from "@/listPage/types";
import { bulkKeyEntries } from "./bulkKeys";
import type { ListMeta } from "@/list/defaults";
import type { BulkScope } from "@/list/useBulkScope";
import type { CopyColumn } from "@/list/bulkCopy";
import type { BulkLayout } from "./bulkLayout";
import type { BulkBarParts } from "./bulkBarParts";
import { rowActionEntries } from "./rowActions";
import type { ListActs } from "./listActs";
import type { RendererHost } from "./renderer";

export interface BulkBarOptions {
  host: RendererHost;
  doctype: string;
  meta: Ref<ListMeta | null | undefined>;
  selection: Ref<string[]>;
  scope: BulkScope;
  rows: Ref<ListRow[]>;
  rowActions: Ref<ListRowAction[]>;
  reload: () => void;
  askDelete: () => void;
  /** What Copy to Clipboard writes: its columns, a cell's text, and the fields a hidden selected row is read with. */
  copy: {
    columns: () => CopyColumn[];
    text: (row: Record<string, unknown>, fieldname: string) => string;
    fields: () => string[];
  };
  /** Acts the renderer adds to its own surface beside the bulk and row ones. */
  extraEntries?: () => ActEntry[];
  /** The row under the pointer or with focus, and the range-aware selection; a surface without a cursor gets no bulk keys. */
  cursor?: Ref<string | null>;
  table?: () => {
    toggle: (name: string) => void;
    extendTo: (name: string) => void;
  } | null;
}

export interface LoadedBulkBar extends BulkBarParts {
  /** The chunk's components and helpers: the bar, its dialogs and the copy's TSV. */
  chunk: typeof import("./bulkBarParts");
  CollabDialog: Component;
}

export interface BulkBar {
  listActs: ListActs;
  /** Whether the bar's More menu is open; the `.` key opens it. */
  menuOpen: Ref<boolean>;
  /** The bar, its status and collaboration actions; null until the lazy chunk loads. */
  parts: ShallowRef<LoadedBulkBar | null>;
  /** The bar's layout; empty until the lazy chunk loads. */
  layout: ComputedRef<BulkLayout>;
  /** Loads the lazy chunk once and resolves whether it loaded; the first selection calls it. */
  load: () => Promise<boolean>;
  /** Loads the chunk early, on pointer or focus, unless a load already failed. */
  prefetch: () => void;
  /** What a run takes: the selected rows, or all the records the filters show. */
  scope: BulkScope;
  /** The most one bulk run takes; the bar disables its actions above it. */
  cap: number;
  /** The person's `bulk_actions` switch is off: the bar draws no action. */
  locked: boolean;
}

const NO_LAYOUT: BulkLayout = { transitions: [], buttons: [], menu: [] };

export function useBulkBar(options: BulkBarOptions): BulkBar {
  const { host, selection, cursor } = options;
  const boot = inject<Boot>("boot")!;
  const parts = shallowRef<LoadedBulkBar | null>(null);
  const layout = computed(() => parts.value?.layout.value ?? NO_LAYOUT);
  host.lists.bulkActions.provideBuiltins(() => parts.value?.builtins() ?? []);

  const menuOpen = ref(false);
  const listActs = host.acts(
    () => [
      ...(selection.value.length && boot.bulk_actions ? parts.value?.entries() ?? [] : []),
      ...rowActionEntries(options.rowActions.value),
      ...(options.extraEntries?.() ?? []),
      ...(cursor
        ? bulkKeyEntries({
            selection,
            cursor,
            shown: (name) =>
              options.rows.value.some((row) => row.name === name),
            locked: !boot.bulk_actions,
            hasMenu: () => layout.value.menu.length > 0,
            menuOpen,
            toggle: (name) => options.table?.()?.toggle(name),
            extendTo: (name) => options.table?.()?.extendTo(name),
          })
        : []),
    ],
    {
      rows: () => options.rows.value,
      selection: () => selection.value,
      selected: () => options.scope.selected(),
      reload: options.reload,
    },
  );

  // The parts' watchers must stop with this component, though they start after an await.
  const partsScope = effectScope();
  let loading: Promise<boolean> | null = null;
  let failed = false;
  function load() {
    loading ??= import("./bulkBarParts")
      .then((chunk) => {
        if (!partsScope.active) return true;
        const made = partsScope.run(() => chunk.bulkBarParts(options, boot, listActs))!;
        const dismiss = () => (made.collab.request.value = null);
        parts.value = { ...made, chunk, CollabDialog: chunk.lazyBulkCollabDialog(dismiss) };
        return true;
      })
      .catch((error) => {
        console.error(error);
        loading = null;
        failed = true;
        return false;
      });
    return loading;
  }
  // A failed prefetch does not retry on each pointer move; the next selection does.
  function prefetch() {
    if (!failed) void load();
  }
  watch(
    () => selection.value.length > 0,
    async (selected) => {
      if (selected && !(await load()))
        toast.error(__("The bulk actions did not load. Reload the page and try again."));
    },
    { immediate: true },
  );

  return {
    listActs,
    menuOpen,
    parts,
    layout,
    load,
    prefetch,
    scope: options.scope,
    cap: boot.bulk_operation_limit,
    locked: !boot.bulk_actions,
  };
}
