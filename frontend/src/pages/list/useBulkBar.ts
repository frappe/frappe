// The list's bulk actions: the built-ins, the acts that run them on the selection, and the bar's layout.
import { computed, inject, ref, type ComputedRef, type Ref } from "vue";
import type { ActEntry } from "@/acts/dispatcher";
import type { Boot } from "@/boot";
import { __ } from "@/i18n";
import type { ListPageApi, ListRow, ListRowAction } from "@/listPage/types";
import { bulkKeyEntries } from "./bulkKeys";
import { bulkScopeOf } from "./bulkScope";
import type { ListMeta } from "@/list/defaults";
import { useBulkStatus, type BulkStatus } from "./bulkStatus";
import type { BulkScope } from "@/list/useBulkScope";
import { exportFilters } from "@/list/bulkExport";
import { layoutBulk, type BulkEntry, type BulkLayout } from "./bulkLayout";
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
  askPrint: () => void;
  askEdit: () => void;
  askExport: () => void;
  copy: () => void;
  /** Acts the renderer adds to its own surface beside the bulk and row ones. */
  extraEntries?: () => ActEntry[];
  /** The row under the pointer or with focus, and the table's range-aware selection; a surface without a cursor (Cards) gets no bulk keys. */
  cursor?: Ref<string | null>;
  table?: () => {
    toggle: (name: string) => void;
    extendTo: (name: string) => void;
  } | null;
}

export interface BulkBar {
  listActs: ListActs;
  /** Whether the bar's More menu is open; the `.` key opens it. */
  menuOpen: Ref<boolean>;
  status: BulkStatus;
  layout: ComputedRef<BulkLayout>;
  /** What a run takes: the selected rows, or all the records the filters show. */
  scope: BulkScope;
  /** The most one bulk run takes; the bar disables its actions above it. */
  cap: number;
  /** The person's `bulk_actions` switch is off: the bar draws no action. */
  locked: boolean;
}

export function useBulkBar(options: BulkBarOptions): BulkBar {
  const { host, selection, askDelete, askEdit, askExport, askPrint, copy, cursor } = options;
  const boot = inject<Boot>("boot")!;
  const { bulkActions: bulkList } = host.lists;
  const cap = boot.bulk_operation_limit;
  const status = useBulkStatus({
    doctype: options.doctype,
    meta: options.meta,
    selection,
    cap,
    locked: !boot.bulk_actions,
    reload: options.reload,
  });

  bulkList.provideBuiltins(() => [
    ...status.items.value,
    {
      name: "print",
      label: __("Print"),
      icon: "lucide-printer",
      group: "output",
      right: "print",
      uncapped: true,
      run: askPrint,
    },
    {
      name: "edit",
      label: __("Edit"),
      icon: "lucide-pencil",
      group: "collaborate",
      button: true,
      right: "write",
      run: askEdit,
    },
    {
      name: "copy",
      label: __("Copy to Clipboard"),
      icon: "lucide-copy",
      group: "output",
      uncapped: true,
      run: copy,
    },
    {
      name: "export",
      label: __("Export"),
      icon: "lucide-download",
      group: "output",
      right: "export",
      uncapped: true,
      run: askExport,
    },
    {
      name: "delete",
      label: __("Delete"),
      icon: "lucide-trash-2",
      group: "danger",
      right: "delete",
      run: askDelete,
    },
  ]);

  const menuOpen = ref(false);
  const scope = bulkScopeOf(selection);
  const listActs = host.acts(
    () => [
      ...(selection.value.length && boot.bulk_actions ? bulkEntries() : []),
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
      reload: options.reload,
    },
  );

  // The palette runs an act with no value or an option, so the wrapper always hands `run` the selection, as the bar does.
  function bulkEntries(): ActEntry[] {
    const all = options.scope.all.value;
    const count = options.scope.count.value;
    return bulkList
      .resolve()
      .filter(({ item }) => item.run)
      .map(({ item, hidden }) => ({
        item: {
          ...item,
          label: item.label && scope.label(item.label),
          argument: undefined,
          palette: all || (count > cap && !item.uncapped) ? (false as const) : item.palette,
          run: (page: ListPageApi) => item.run!(page, scope.selected()),
        },
        hidden,
      }));
  }

  // Select all disables what takes row names: it would run on the loaded rows alone. Delete, Edit, Export and Print read the scope; Print has its own cap, checked when it opens.
  const readsScope = (run: unknown) => run === askDelete || run === askEdit || run === askExport || run === askPrint;
  // The exporter takes no `or_filters`: it would export more than the filters show.
  const disabled = ({ name, uncapped, run }: { name: string; uncapped?: boolean; run?: unknown }) =>
    (name === "export" && exportFilters(options.scope.selected()) === null) ||
    (options.scope.all.value && !readsScope(run)) ||
    (!uncapped && options.scope.count.value > cap);
  const locked = !boot.bulk_actions;
  const entries = computed<BulkEntry[]>(() =>
    locked
      ? []
      : bulkList.visible().flatMap((item) => {
          const act = listActs.drawn(item.name);
          if (!act) return [];
          return [
            {
              name: item.name,
              label: item.label ?? item.name,
              icon: act.icon,
              group: item.group,
              button: item.button,
              disabled: disabled(item),
              onClick: () => listActs.perform(act, scope.selected()),
            },
          ];
        }),
  );

  const layout = computed(() => layoutBulk(entries.value, options.doctype));
  return { listActs, menuOpen, status, layout, scope: options.scope, cap, locked };
}
