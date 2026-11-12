// The bulk bar's lazy half: the built-in bulk actions, their palette acts, the bar's layout, the bar and its dialogs.
// `useBulkBar` loads it on the first selection, or earlier when the pointer or focus enters the list.
import { toast } from "frappe-ui";
import { computed, defineAsyncComponent, type Component, type ComputedRef } from "vue";
import type { ActEntry } from "@/acts/dispatcher";
import type { Boot } from "@/boot";
import { __ } from "@/i18n";
import { exportFilters } from "@/list/bulkExport";
import type { ListPageAction, ListPageApi } from "@/listPage/types";
import { useBulkCollaboration, type BulkCollaboration } from "./bulkCollaboration";
import { layoutBulk, type BulkEntry, type BulkLayout } from "./bulkLayout";
import { useBulkPrint, type BulkPrint } from "./bulkPrint";
import { useBulkStatus, type BulkStatus } from "./bulkStatus";
import type { ListActs } from "./listActs";
import type { BulkBarOptions } from "./useBulkBar";

export { default as BulkBar } from "./BulkBar.vue";
export { PrintDialog } from "./bulkPrint";
export { lazyBulkCollabDialog } from "./lazyBulkCollabDialog";
export { selectionTsv, withHiddenRows } from "@/list/bulkCopy";

export const DeleteDialog = lazyDialog(
  () => import("./DeleteDialog.vue"),
  __("The delete dialog did not load. Reload the page and try again."),
);
export const EditDialog = lazyDialog(
  () => import("./EditDialog.vue"),
  __("The edit dialog did not load. Reload the page and try again."),
);
export const ExportDialog = lazyDialog(
  () => import("./ExportDialog.vue"),
  __("The export dialog did not load. Reload the page and try again."),
);

export interface BulkBarParts {
  status: BulkStatus;
  /** The assign, tag, follow, share and seen actions: their dialog's request. */
  collab: BulkCollaboration;
  /** The Print dialog's state; Print asks it to open. */
  print: BulkPrint;
  /** The items `bulkActions` resolves its built-ins from. */
  builtins: () => ListPageAction[];
  /** The bulk acts on the selection, for the palette. */
  entries: () => ActEntry[];
  layout: ComputedRef<BulkLayout>;
}

export function bulkBarParts(options: BulkBarOptions, boot: Boot, listActs: ListActs): BulkBarParts {
  const { selection, askDelete, askEdit, askExport, copy } = options;
  const { bulkActions: bulkList } = options.host.lists;
  const cap = boot.bulk_operation_limit;
  const locked = !boot.bulk_actions;
  const status = useBulkStatus({
    doctype: options.doctype,
    meta: options.meta,
    selection,
    scope: options.scope,
    cap,
    locked,
    reload: options.reload,
  });

  const collab = useBulkCollaboration(
    options.doctype,
    () => ({
      selection: options.scope.selected(),
      count: options.scope.count.value,
      all: options.scope.all.value,
      approx: options.scope.approx.value,
    }),
    boot.session.user.name,
  );
  const print = useBulkPrint(options.scope, boot.max_bulk_print_docs);
  const askPrint = print.ask;

  const builtins = (): ListPageAction[] => {
    const all = everyBuiltin();
    return options.meta.value?.allow_bulk_edit === false
      ? all.filter(({ name }) => name !== "edit" && name !== "delete")
      : all;
  };

  const everyBuiltin = (): ListPageAction[] => [
    ...status.items.value,
    ...collab.items(),
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
  ];

  // The palette runs an act with no value or an option, so the wrapper always hands `run` the selection, as the bar does.
  function entries(): ActEntry[] {
    return bulkList
      .resolve()
      .filter(({ item }) => item.run)
      .map(({ item, hidden }) => ({
        item: {
          ...item,
          label: item.label && scopedLabel(item.label),
          argument: undefined,
          palette: disabled(item) ? (false as const) : item.palette,
          run: (page: ListPageApi) => item.run!(page, [...selection.value]),
        },
        hidden,
      }));
  }

  function scopedLabel(label: string) {
    const { scope } = options;
    return scope.all.value
      ? __("{0} all {1} matching", [label, scope.totalText.value])
      : __("{0} {1} selected", [label, scope.count.value]);
  }

  // Select all disables what takes row names: it would run on the loaded rows alone. Print has its own cap, checked when it opens.
  const readsScope = (run: unknown) =>
    [askDelete, askEdit, askExport, askPrint].includes(run as never) ||
    status.owns(run as ListPageAction["run"]) ||
    collab.takesScope(run);
  // The exporter takes no `or_filters`: it would export more than the filters show.
  const disabled = ({ name, uncapped, run }: { name: string; uncapped?: boolean; run?: unknown }) =>
    (name === "export" && exportFilters(options.scope.selected()) === null) ||
    (options.scope.all.value && !readsScope(run)) ||
    (!uncapped && options.scope.count.value > cap);

  const drawn = computed<BulkEntry[]>(() =>
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
              onClick: () => listActs.perform(act, [...selection.value]),
            },
          ];
        }),
  );

  const layout = computed(() => layoutBulk(drawn.value, options.doctype));
  return { status, collab, print, builtins, entries, layout };
}

function lazyDialog(loader: () => Promise<Component>, message: string) {
  return defineAsyncComponent({
    loader,
    onError: (_error, _retry, fail) => {
      toast.error(message);
      fail();
    },
  });
}
