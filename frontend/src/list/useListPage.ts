// One doctype's list: the state the controls edit, seeded from the app default under the site's
// and the person's stored rows, mirrored to the URL query, and written back on the person's acts.
import { useDoctypeMeta } from "@framework/ui/composables/useDoctypeMeta";
import { useDocPermissions } from "@framework/ui/composables/useDocPermissions";
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
import {
	columnsFrom,
	quickFilterFieldsFrom,
	sortFrom,
	toStoredColumns,
	toStoredQuickFilterFields,
	type ListSettings,
	type ListSettingsKey,
} from "./storedSettings";
import { useListRows, type ListRow, type ListRows } from "./useListRows";
import { useListSettings } from "./useListSettings";

export interface DeleteOutcome {
	deleted: string[];
	failed: { name: string; error: string }[];
}

export interface ListPage extends ListRows {
	/** Written to the URL query. */
	filters: Ref<FilterCondition[]>;
	/** Written to the URL query and, on the person's own change, to their row. */
	sort: Ref<Sort[]>;
	/** Written to the person's row. */
	columns: Ref<ListColumn[]>;
	/** Written to the person's row when customizing ends. */
	quickFilterFields: Ref<FilterField[] | undefined>;
	customizing: Ref<boolean>;
	selection: Ref<string[]>;
	/** Kept in the history entry. */
	pageSize: Ref<number>;
	/** The filters and sort the rows belong to, as one string: the session memory's key. */
	rowsKey: () => string;
	metaError: ComputedRef<string | null>;
	/** True when the person's own row holds columns. */
	columnsCustomized: ComputedRef<boolean>;
	/** Clears the person's columns, so the site's or the app's show. */
	resetColumns: () => Promise<void>;
	resizeColumn: (fieldname: string, width: string) => void;
	resetColumnWidth: (fieldname: string) => void;
	/** The site's defaults, which everyone without their own inherits; a System Manager's act. */
	saveForSite: (settings: ListSettings) => Promise<void>;
	resetForSite: (key: ListSettingsKey) => Promise<void>;
	rowLink: (row: ListRow) => RouteLocationRaw;
	/** Deletes the selection one row at a time; the page confirms first. */
	deleteSelection: () => Promise<DeleteOutcome>;
}

export function useListPage(doctype: string): ListPage {
	const route = useRoute();
	const router = useRouter();
	const { meta, error } = useDoctypeMeta(doctype);
	const permissions = useDocPermissions(doctype);
	const settings = useListSettings(doctype);
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
	// What the page last set itself, per key: a change that matches it is not the person's act.
	const applied: Partial<Record<ListSettingsKey, string>> = {};
	// Set once meta lands: the rows an earlier visit to this query showed, by Back or a breadcrumb.
	let remembered: ReturnType<typeof recallRows>;

	const ready = computed(
		() => Boolean(listMeta.value) && settings.loaded.value && !permissions.loading.value
	);

	const readable = (fieldname: string) => {
		const field = fields.value.find((one) => one.fieldname === fieldname);
		return !field || permissions.fieldAccess(field) !== "none";
	};

	const defaults = computed(() =>
		listMeta.value ? defaultColumns(listMeta.value, contributed) : []
	);

	/** The columns the tiers resolve to: the person's, else the site's, else the app default. */
	function resolvedColumns(): ListColumn[] {
		const stored = columnsFrom(settings.stored.value.columns, fields.value, readable);
		return stored.length ? stored : defaults.value;
	}

	function resolvedSort(): Sort[] {
		const stored = sortFrom(settings.stored.value.sort, fields.value, readable);
		return stored.length ? stored : defaultSort(listMeta.value!);
	}

	function resolvedQuickFilterFields(): FilterField[] | undefined {
		const stored = settings.stored.value.quick_filter_fields;
		if (!stored) return undefined;
		return quickFilterFieldsFrom(stored, doctype, fields.value, readable);
	}

	function applyStored() {
		columns.value = resolvedColumns();
		applied.columns = JSON.stringify(toStoredColumns(columns.value));
		quickFilterFields.value = resolvedQuickFilterFields();
		applied.quick_filter_fields = JSON.stringify(
			quickFilterFields.value && toStoredQuickFilterFields(quickFilterFields.value)
		);
	}

	function readQuery(value: ListMeta) {
		const address = addressFromQuery(route.query, doctype, value.fields ?? []);
		filters.value = address.filters ?? [];
		readSort();
	}

	/** After a row changed under the page: the sort follows, a filter still being typed stays. */
	function readSort() {
		const address = addressFromQuery(route.query, doctype, fields.value);
		sort.value = address.sort ?? resolvedSort();
		applied.sort = JSON.stringify(sort.value);
	}

	watch(
		ready,
		(value) => {
			if (!value || seeded.value) return;
			applyStored();
			readQuery(listMeta.value!);
			remembered = recallRows(doctype, stateKey());
			if (remembered && readListMemory().pageSize == null) pageSize.value = remembered.pageSize;
			seeded.value = true;
		},
		{ immediate: true }
	);

	// Only a query the page did not write itself is read back: Back, Forward, a pasted link.
	watch(
		() => route.query,
		(query) => {
			if (seeded.value && !sameQuery(query, stateQuery())) readQuery(listMeta.value!);
		}
	);

	// A replace, so the tweak is not a step Back has to undo. A landed write moves the resolved
	// sort, so the URL is spelled again and a `_sort` that became the default goes.
	watch([filters, sort, settings.stored], writeQuery, { deep: true });

	function writeQuery() {
		if (!seeded.value || sameQuery(route.query, stateQuery())) return;
		router.replace({ query: stateQuery(), hash: route.hash }).catch(() => {});
	}

	/** The query the state spells: foreign keys kept, the resolved sort left unwritten. */
	function stateQuery() {
		const owned = ownedKeys(doctype, fields.value);
		const kept = Object.fromEntries(
			Object.entries(route.query).filter(([key]) => !owned.has(key))
		);
		const written = sameSort(sort.value, resolvedSort()) ? [] : sort.value;
		return { ...kept, ...queryFromAddress({ filters: filters.value, sort: written }) };
	}

	function stateKey() {
		return JSON.stringify(queryFromAddress({ filters: filters.value, sort: sort.value }));
	}

	// The person's own acts write; a value the page set itself, from a row or the URL, does not.
	watch(columns, (value) => persist("columns", toStoredColumns(value)), { deep: true });
	watch(sort, (value) => persist("sort", value), { deep: true });
	watch(customizing, (now, before) => {
		if (before && !now && quickFilterFields.value) {
			persist("quick_filter_fields", toStoredQuickFilterFields(quickFilterFields.value));
		}
	});

	function persist<Key extends ListSettingsKey>(key: Key, value: ListSettings[Key]) {
		const json = JSON.stringify(value);
		if (!seeded.value || applied[key] === json) return;
		applied[key] = json;
		settings.save({ [key]: value });
	}

	const rows = useListRows(doctype, () => {
		if (!seeded.value) return null;
		return {
			key: stateKey(),
			fields: fetchFields(columns.value),
			filters: filtersDict(filters.value),
			orderBy: serializeOrderBy(sort.value.length ? sort.value : resolvedSort()),
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
		columnsCustomized: computed(() => settings.has("user", "columns")),
		resetColumns: async () => {
			await settings.reset("columns");
			applyStored();
			readSort();
		},
		resizeColumn: (fieldname, width) =>
			(columns.value = applyColumnWidth(columns.value, fieldname, width) as ListColumn[]),
		resetColumnWidth: (fieldname) =>
			(columns.value = clearColumnWidth(columns.value, fieldname) as ListColumn[]),
		saveForSite: async (value) => {
			await settings.saveForSite(value);
			applyStored();
			readSort();
		},
		resetForSite: async (key) => {
			await settings.resetForSite(key);
			applyStored();
			readSort();
		},
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
