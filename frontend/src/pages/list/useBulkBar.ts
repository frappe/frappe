// The list's bulk actions: the built-ins, the acts that run them on the selection, and the bar's layout.
import { computed, inject, ref, type ComputedRef, type Ref } from "vue";
import type { ActEntry } from "@/acts/dispatcher";
import type { Boot } from "@/boot";
import { __ } from "@/i18n";
import type { ListPageApi, ListRow, ListRowAction } from "@/listPage/types";
import { bulkKeyEntries } from "./bulkKeys";
import { bulkScopeOf } from "./bulkScope";
import { layoutBulk, type BulkEntry, type BulkLayout } from "./bulkLayout";
import { rowActionEntries } from "./rowActions";
import type { ListActs } from "./listActs";
import type { RendererHost } from "./renderer";

export interface BulkBarOptions {
	host: RendererHost;
	doctype: string;
	selection: Ref<string[]>;
	rows: Ref<ListRow[]>;
	rowActions: Ref<ListRowAction[]>;
	reload: () => void;
	askDelete: () => void;
	/** Acts the renderer adds to its own surface beside the bulk and row ones. */
	extraEntries?: () => ActEntry[];
	/** The row under the pointer or with focus, and the table's range-aware selection; a surface without a cursor (Cards) gets no bulk keys. */
	cursor?: Ref<string | null>;
	table?: () => { toggle: (name: string) => void; extendTo: (name: string) => void } | null;
}

export interface BulkBar {
	listActs: ListActs;
	/** Whether the bar's More menu is open; the `.` key opens it. */
	menuOpen: Ref<boolean>;
	layout: ComputedRef<BulkLayout>;
	/** The most one bulk run takes; the bar disables its actions above it. */
	cap: number;
	/** The person's `bulk_actions` switch is off: the bar draws no action. */
	locked: boolean;
}

export function useBulkBar(options: BulkBarOptions): BulkBar {
	const { host, selection, askDelete, cursor } = options;
	const boot = inject<Boot>("boot")!;
	const { bulkActions: bulkList } = host.lists;

	bulkList.provideBuiltins(() => [
		{
			name: "delete",
			label: __("Delete"),
			icon: "lucide-trash-2",
			group: "danger",
			right: "delete",
			run: askDelete,
		},
	]);

	const cap = boot.bulk_operation_limit;
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
						shown: (name) => options.rows.value.some((row) => row.name === name),
						locked: !boot.bulk_actions,
						hasMenu: () => layout.value.menu.length > 0,
						menuOpen,
						toggle: (name) => options.table?.()?.toggle(name),
						extendTo: (name) => options.table?.()?.extendTo(name),
					})
				: []),
		],
		{ rows: () => options.rows.value, selection: () => selection.value, reload: options.reload }
	);

	// The palette runs an act with no value or an option, so the wrapper always hands `run` the selection, as the bar does.
	function bulkEntries(): ActEntry[] {
		const over = selection.value.length > cap;
		return bulkList
			.resolve()
			.filter(({ item }) => item.run)
			.map(({ item, hidden }) => ({
				item: {
					...item,
					label: item.label && scope.label(item.label),
					argument: undefined,
					palette: over ? (false as const) : item.palette,
					run: (page: ListPageApi) => item.run!(page, scope.selected()),
				},
				hidden,
			}));
	}

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
							disabled: selection.value.length > cap,
							onClick: () => listActs.perform(act, scope.selected()),
						},
					];
			  })
	);

	const layout = computed(() => layoutBulk(entries.value, options.doctype));
	return { listActs, menuOpen, layout, cap, locked };
}
