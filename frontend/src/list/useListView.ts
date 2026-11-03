// The List type's rows area: its columns from the view's settings, and the rows the view's filters
// and sort read, with the selection, the page size and the delete.
import { applyColumnWidth, clearColumnWidth } from "@framework/ui/ColumnSettings";
import type { ListColumn } from "@framework/ui/experimental/List";
import { getFilterableFields, serializeFilters, type FilterCondition } from "@framework/ui/Filter";
import type { RawMetaField } from "@framework/ui/FormLayout";
import { serializeOrderBy } from "@framework/ui/SortBy";
import { useDocPermissions } from "@framework/ui/useDocPermissions";
import { useDoctypeMeta } from "@framework/ui/useDoctypeMeta";
import { computed, ref, watch, type ComputedRef, type Ref, type WritableComputedRef } from "vue";
import type { RouteLocationRaw } from "vue-router";
import { listHandlersFor } from "@/contributions/registry";
import type { RowAction } from "@/contributions/types";
import { routeFor } from "@/router/routeFor";
import {
	cellCurrency,
	cellMark,
	type CellCurrency,
	type CellMark,
	contributedRowActions,
	defaultColumns,
	fetchFields,
	type ListMeta,
} from "./defaults";
import { readListMemory, recallRows, rememberRows, writeListMemory } from "./pageState";
import { completeFilters, queryFromAddress } from "./query";
import { columnsFrom, toStoredColumns } from "./storedSettings";
import { useListRows, type ListRow, type ListRows } from "./useListRows";
import type { View } from "./view";

export interface DeleteOutcome {
	deleted: string[];
	failed: { name: string; error: string }[];
}

export interface ListView extends ListRows {
	/** The view's `columns` key, else the app default; a change is written to the view. */
	columns: WritableComputedRef<ListColumn[]>;
	/** The row actions the apps contributed for this doctype. */
	rowActions: RowAction[];
	/** The field a column shows, a standard one such as `creation` included. */
	fieldOf: (fieldname: string) => RawMetaField | undefined;
	/** What a column's cell shows before its text; see `cellMark`. */
	markOf: (fieldname: string) => CellMark | undefined;
	/** Where a Currency column's cell finds its currency in the row; see `cellCurrency`. */
	currencyOf: (fieldname: string) => CellCurrency | undefined;
	selection: Ref<string[]>;
	/** Kept in the history entry. */
	pageSize: Ref<number>;
	/** The filters and sort the rows belong to, as one string: the session memory's key. */
	rowsKey: () => string;
	/** True when the person's own row holds columns. */
	columnsCustomized: ComputedRef<boolean>;
	/** Clears the person's columns, so the site's or the app's show. */
	resetColumns: () => Promise<void>;
	resizeColumn: (fieldname: string, width: string) => void;
	resetColumnWidth: (fieldname: string) => void;
	rowLink: (row: ListRow) => RouteLocationRaw;
	/** Deletes the selection one row at a time; the page confirms first. */
	deleteSelection: () => Promise<DeleteOutcome>;
}

export function useListView(view: View): ListView {
	const { doctype } = view;
	const { meta } = useDoctypeMeta(doctype);
	const permissions = useDocPermissions(doctype);
	const listMeta = computed(() => meta.value as ListMeta | null);
	const fields = computed(() => listMeta.value?.fields ?? []);
	const contributed = listHandlersFor(doctype).map(({ handlers }) => handlers);
	const rowActions = contributedRowActions(contributed);

	const readable = (fieldname: string) => {
		const field = fields.value.find((one) => one.fieldname === fieldname);
		return !field || permissions.fieldAccess(field) !== "none";
	};

	const readableActions = () =>
		rowActions.map((action) => ({ ...action, fields: action.fields.filter(readable) }));

	const defaults = computed(() =>
		listMeta.value ? defaultColumns(listMeta.value, contributed) : []
	);

	/** The columns the tiers resolve to: the person's, else the site's, else the app default. */
	const columns = computed<ListColumn[]>({
		get: () => {
			const stored = columnsFrom(view.settings.value.columns, fields.value, readable);
			return stored.length ? stored : defaults.value;
		},
		// A rename alone, or the app default handed back unchanged, is not the person's change.
		set: (value) => {
			const stored = toStoredColumns(value);
			if (JSON.stringify(stored) !== JSON.stringify(toStoredColumns(columns.value)))
				view.update({ columns: stored });
		},
	});

	const selection = ref<string[]>([]);
	const pageSize = ref(readListMemory().pageSize ?? 20);

	const stateKey = () =>
		JSON.stringify(queryFromAddress({ filters: view.filters.value, sort: view.sort.value }));

	// A breadcrumb has no history entry; an earlier visit gives the page size. Made before the
	// rows, so the first read already asks for it.
	watch(
		view.seeded,
		(seeded) => {
			const remembered = seeded && recallRows(doctype, stateKey());
			if (remembered && readListMemory().pageSize == null) pageSize.value = remembered.pageSize;
		},
		{ immediate: true }
	);

	const rows = useListRows(doctype, () => {
		if (!view.seeded.value) return null;
		return {
			key: stateKey(),
			fields: fetchFields(columns.value, readableActions(), listMeta.value ?? {}, readable),
			filters: filtersDict(view.filters.value),
			orderBy: serializeOrderBy(view.sort.value),
			limit: pageSize.value,
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
	// Immediate: with meta in memory the first read, and so its key, starts before this watch.
	watch(
		[pageSize, rows.loadedKey],
		([size, key]) => {
			if (key) rememberRows(doctype, { query: key, pageSize: size });
		},
		{ immediate: true }
	);

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
		columns,
		rowActions,
		fieldOf: (fieldname) =>
			fields.value.find((one) => one.fieldname === fieldname) ??
			getFilterableFields([], doctype).find((one) => one.fieldname === fieldname),
		markOf: (fieldname) => cellMark(fieldname, listMeta.value ?? {}),
		currencyOf: (fieldname) => cellCurrency(fieldname, listMeta.value ?? {}, readable),
		selection,
		pageSize,
		rowsKey,
		columnsCustomized: computed(() => view.customized("columns")),
		resetColumns: () => view.reset("columns"),
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
