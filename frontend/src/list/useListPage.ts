// One doctype's list: the state the controls edit, seeded from meta and a contributed `list.js`,
// with filters and sort mirrored to the URL query. Every act is a model or a plain function.
import { useDoctypeMeta } from "@framework/ui/composables/useDoctypeMeta";
import { applyColumnWidth, clearColumnWidth } from "@framework/ui/ColumnSettings";
import type { ListColumn } from "@framework/ui/experimental/List";
import { serializeFilters, type FilterCondition, type FilterField } from "@framework/ui/Filter";
import { serializeOrderBy, type Sort } from "@framework/ui/SortBy";
import { computed, ref, watch, type ComputedRef, type Ref } from "vue";
import { useRoute, useRouter, type RouteLocationRaw } from "vue-router";
import { listHandlersFor } from "@/contributions/registry";
import { routeFor } from "@/router/routeFor";
import { defaultColumns, defaultSort, fetchFields, sameSort, type ListMeta } from "./defaults";
import { readListMemory, recallRows, rememberRows, writeListMemory } from "./pageState";
import { addressFromQuery, completeFilters, ownedKeys, queryFromAddress, sameQuery } from "./query";
import { useListRows, type ListRow, type ListRows } from "./useListRows";

export interface DeleteOutcome {
	deleted: string[];
	failed: { name: string; error: string }[];
}

export interface ListPage extends ListRows {
	/** Written to the URL query. */
	filters: Ref<FilterCondition[]>;
	/** Written to the URL query; the header click edits the same list. */
	sort: Ref<Sort[]>;
	/** In memory for the visit. */
	columns: Ref<ListColumn[]>;
	quickFilterFields: Ref<FilterField[] | undefined>;
	customizing: Ref<boolean>;
	selection: Ref<string[]>;
	/** Kept in the history entry. */
	pageSize: Ref<number>;
	/** The filters and sort the rows belong to, as one string: the session memory's key. */
	rowsKey: () => string;
	metaError: ComputedRef<string | null>;
	columnsCustomized: ComputedRef<boolean>;
	resetColumns: () => void;
	resizeColumn: (fieldname: string, width: string) => void;
	resetColumnWidth: (fieldname: string) => void;
	rowLink: (row: ListRow) => RouteLocationRaw;
	/** Deletes the selection one row at a time; the page confirms first. */
	deleteSelection: () => Promise<DeleteOutcome>;
}

export function useListPage(doctype: string): ListPage {
	const route = useRoute();
	const router = useRouter();
	const { meta, error } = useDoctypeMeta(doctype);
	const listMeta = computed(() => meta.value as ListMeta | null);
	const fields = computed(() => listMeta.value?.fields ?? []);
	const contributed = listHandlersFor(doctype).map(({ handlers }) => handlers);

	const filters = ref<FilterCondition[]>([]);
	const sort = ref<Sort[]>([]);
	const columns = ref<ListColumn[]>([]);
	const quickFilterFields = ref<FilterField[] | undefined>();
	const customizing = ref(false);
	const selection = ref<string[]>([]);
	const pageSize = ref(readListMemory().pageSize ?? 20);
	const seeded = ref(false);
	// Set once meta lands: the rows an earlier visit to this query showed, by Back or a breadcrumb.
	let remembered: ReturnType<typeof recallRows>;

	watch(
		listMeta,
		(value) => {
			if (!value || seeded.value) return;
			columns.value = defaultColumns(value, contributed);
			readQuery(value);
			remembered = recallRows(doctype, stateKey());
			if (remembered && readListMemory().pageSize == null) pageSize.value = remembered.pageSize;
			seeded.value = true;
		},
		{ immediate: true }
	);

	function readQuery(value: ListMeta) {
		const address = addressFromQuery(route.query, doctype, value.fields ?? []);
		filters.value = address.filters ?? [];
		sort.value = address.sort ?? defaultSort(value);
	}

	// Only a query the page did not write itself is read back: Back, Forward, a pasted link.
	watch(
		() => route.query,
		(query) => {
			if (seeded.value && !sameQuery(query, stateQuery())) readQuery(listMeta.value!);
		}
	);

	// A replace, so the tweak is not a step Back has to undo.
	watch([filters, sort], writeQuery, { deep: true });

	function writeQuery() {
		if (!seeded.value || sameQuery(route.query, stateQuery())) return;
		router.replace({ query: stateQuery(), hash: route.hash }).catch(() => {});
	}

	/** The query the state spells: foreign keys kept, the default sort left unwritten. */
	function stateQuery() {
		const owned = ownedKeys(doctype, fields.value);
		const kept = Object.fromEntries(
			Object.entries(route.query).filter(([key]) => !owned.has(key))
		);
		const written = sameSort(sort.value, defaultSort(listMeta.value!)) ? [] : sort.value;
		return { ...kept, ...queryFromAddress({ filters: filters.value, sort: written }) };
	}

	function stateKey() {
		return JSON.stringify(queryFromAddress({ filters: filters.value, sort: sort.value }));
	}

	const rows = useListRows(doctype, () => {
		if (!seeded.value) return null;
		return {
			key: stateKey(),
			fields: fetchFields(columns.value),
			filters: filtersDict(filters.value),
			orderBy: serializeOrderBy(sort.value.length ? sort.value : defaultSort(listMeta.value!)),
			limit: pageSize.value,
			restore: remembered?.shown,
		};
	});

	watch(pageSize, (size) => writeListMemory({ pageSize: size }));
	// The entry's offset belongs to the query it was scrolled on; a new query on the same entry
	// starts at the top, or Back would land the old offset on the new rows.
	watch(rows.loadedKey, (_key, previous) => {
		if (previous != null) writeListMemory({ scrollTop: 0 });
	});
	// Keyed by the rows' own query: while a typed filter waits out its debounce, the state is
	// already the new query and the rows are still the old one.
	const rowsKey = () => rows.loadedKey.value ?? stateKey();
	watch([pageSize, rows.shown, rows.loadedKey], ([size, shown]) => {
		if (shown) rememberRows(doctype, { query: rowsKey(), pageSize: size, shown });
	});

	// A row that left the page leaves the selection; the rest stay selected across a load-more.
	watch(rows.rows, (current) => {
		const present = new Set(current.map((row) => row.name));
		selection.value = selection.value.filter((name) => present.has(name));
	});

	const defaults = computed(() =>
		listMeta.value ? defaultColumns(listMeta.value, contributed) : []
	);

	async function deleteSelection(): Promise<DeleteOutcome> {
		const outcome: DeleteOutcome = { deleted: [], failed: [] };
		for (const name of selection.value) {
			try {
				await rows.remove(name);
				outcome.deleted.push(name);
			} catch (failure) {
				outcome.failed.push({ name, error: messageOf(failure) });
			}
		}
		selection.value = [];
		rows.reload();
		return outcome;
	}

	return {
		...rows,
		filters,
		sort,
		columns,
		quickFilterFields,
		customizing,
		selection,
		pageSize,
		rowsKey,
		metaError: computed(() => (error.value ? messageOf(error.value) : null)),
		columnsCustomized: computed(
			() => JSON.stringify(columns.value) !== JSON.stringify(defaults.value)
		),
		resetColumns: () => (columns.value = defaults.value),
		resizeColumn: (fieldname, width) =>
			(columns.value = applyColumnWidth(columns.value, fieldname, width) as ListColumn[]),
		resetColumnWidth: (fieldname) =>
			(columns.value = clearColumnWidth(columns.value, fieldname) as ListColumn[]),
		rowLink: (row) => routeFor(doctype, row.name),
		deleteSelection,
	};
}

/** The object form `useList` takes; it holds one condition per field, so a second one is lost. */
function filtersDict(filters: FilterCondition[]): Record<string, unknown> {
	const dict: Record<string, unknown> = {};
	for (const [fieldname, operator, value] of serializeFilters(completeFilters(filters))) {
		dict[fieldname] = [operator, value];
	}
	return dict;
}

function messageOf(failure: unknown): string {
	if (failure instanceof Error) return failure.message;
	return String(failure);
}
