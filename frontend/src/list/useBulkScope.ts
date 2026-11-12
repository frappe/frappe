// What a bulk run takes: the selected rows, or, after "Select all N", every record the filters show.
import { computed, ref, watch, type ComputedRef, type Ref } from "vue";
import type { BulkSelection } from "@framework/ui/api";
import type { ListRow } from "./useListRows";

export interface BulkScopeOptions {
	selection: Ref<string[]>;
	rows: () => ListRow[];
	/** The list's filters, as the query sends them: the same ones the rows were read with. */
	filters: () => Record<string, unknown>;
	hasNextPage: () => boolean;
	totalCount: () => number;
	/** The total is a floor ("10,000+") or unknown. */
	totalApprox: () => boolean;
}

export interface BulkScope {
	/** The selection covers every record the filters show, not just the loaded rows. */
	all: Ref<boolean>;
	/** How many records a run takes. */
	count: ComputedRef<number>;
	/** Every record the filters show: what "Select all N" selects. */
	total: ComputedRef<number>;
	/** The total is a floor: shown with a "+". */
	approx: ComputedRef<boolean>;
	/** Every loaded row is selected and more match: the bar offers "Select all N". */
	canSelectAll: ComputedRef<boolean>;
	selectAll: () => void;
	clear: () => void;
	/** The request body's selection: the filters after "Select all N", else the names, frozen now. */
	selected: () => BulkSelection;
}

export function useBulkScope(options: BulkScopeOptions): BulkScope {
	const { selection, rows } = options;
	const all = ref(false);

	const total = computed(() => options.totalCount());
	const count = computed(() => (all.value ? total.value : selection.value.length));
	const approx = computed(() => options.totalApprox());
	const canSelectAll = computed(
		() =>
			!all.value &&
			rows().length > 0 &&
			selection.value.length === rows().length &&
			options.hasNextPage()
	);

	// A row that left the page leaves the selection; after "Select all N", a loaded page joins it.
	watch(rows, (current) => {
		const present = new Set(current.map((row) => row.name));
		selection.value = all.value ? [...present] : selection.value.filter((name) => present.has(name));
	});
	// Any other change to the selection means it no longer is everything.
	watch(selection, (names) => {
		if (names.length !== rows().length) all.value = false;
	});
	// A new filter is a new set of records: nothing carries over.
	watch(
		() => JSON.stringify(options.filters()),
		() => clear()
	);

	function clear() {
		all.value = false;
		selection.value = [];
	}

	return {
		all,
		count,
		total,
		approx,
		canSelectAll,
		selectAll: () => (all.value = true),
		clear,
		selected: () => (all.value ? { filters: options.filters() } : { names: [...selection.value] }),
	};
}
