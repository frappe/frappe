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
	/** The total is a floor ("10,000+"). */
	totalApprox: () => boolean;
	/** The rows, the total and the filters all describe one query; "Select all N" waits for it. */
	exact: () => boolean;
}

export interface BulkScope {
	all: Ref<boolean>;
	count: ComputedRef<number>;
	total: ComputedRef<number>;
	approx: ComputedRef<boolean>;
	/** The total as people read it: "1,240", or "10,000+" when it is a floor. */
	totalText: ComputedRef<string>;
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
	const totalText = computed(() => total.value.toLocaleString() + (approx.value ? "+" : ""));
	const canSelectAll = computed(
		() =>
			!all.value &&
			options.exact() &&
			rows().length > 0 &&
			selection.value.length === rows().length &&
			options.hasNextPage()
	);

	watch(rows, (current) => {
		if (all.value && !current.length) return;
		const present = new Set(current.map((row) => row.name));
		selection.value = all.value ? [...present] : selection.value.filter((name) => present.has(name));
	});
	watch(selection, (names) => {
		if (names.length !== rows().length) all.value = false;
	});
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
		totalText,
		canSelectAll,
		selectAll: () => (all.value = true),
		clear,
		selected: () => (all.value ? { filters: options.filters() } : { names: [...selection.value] }),
	};
}
