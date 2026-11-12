// The list's bulk actions: the built-ins, the acts that run them on the selection, and the bar's layout.
import { computed, inject, type ComputedRef, type Ref } from "vue";
import type { Boot } from "@/boot";
import { __ } from "@/i18n";
import type { ListRow, ListRowAction } from "@/listPage/types";
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
}

export interface BulkBar {
	listActs: ListActs;
	layout: ComputedRef<BulkLayout>;
	/** The most one bulk run takes; the bar disables its actions above it. */
	cap: number;
	/** The person's `bulk_actions` switch is off: the bar draws no action. */
	locked: boolean;
}

export function useBulkBar(options: BulkBarOptions): BulkBar {
	const { host, selection, askDelete } = options;
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

	const listActs = host.acts(
		() => [
			...(selection.value.length ? bulkEntries() : []),
			...rowActionEntries(options.rowActions.value),
		],
		{ rows: () => options.rows.value, selection: () => selection.value, reload: options.reload }
	);

	function bulkEntries() {
		return bulkList
			.resolve()
			.filter(({ item }) => item.run)
			.map(({ item, hidden }) => ({ item, hidden }));
	}

	const cap = boot.bulk_operation_limit;
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
							label: act.label!,
							icon: act.icon,
							group: item.group,
							button: item.button,
							disabled: selection.value.length > cap,
							onClick: () => listActs.perform(act, [...selection.value]),
						},
					];
			  })
	);

	return { listActs, layout: computed(() => layoutBulk(entries.value, options.doctype)), cap, locked };
}
