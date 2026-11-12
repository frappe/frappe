// The List type's rows area: its columns from the view's settings, and the rows the view's filters
// and sort read, with the selection, the page size and the delete.
import { applyColumnWidth, clearColumnWidth, getColumnAlign } from "@framework/ui/ColumnSettings";
import type { ListColumn } from "@framework/ui/experimental/List";
import { getFilterableFields, serializeFilters, type FilterCondition } from "@framework/ui/Filter";
import type { RawMetaField } from "@framework/ui/FormLayout";
import { serializeOrderBy } from "@framework/ui/SortBy";
import { useDocPermissions } from "@framework/ui/useDocPermissions";
import { useDoctypeMeta } from "@framework/ui/useDoctypeMeta";
import { currentSession } from "@framework/ui/useSession";
import { computed, ref, watch, type ComputedRef, type Ref, type WritableComputedRef } from "vue";
import type { RouteLocationRaw } from "vue-router";
import type { ListPageLists } from "@/listPage/createListPage";
import { listScriptsOf } from "@/listPage/scriptLoader";
import type { ListPageColumn, ListRowAction } from "@/listPage/types";
import { rowActionFields } from "@/listPage/types";
import { routeFor } from "@/router/routeFor";
import {
	cellCurrency,
	cellMark,
	cellTitle,
	type CellMark,
	defaultColumns,
	fetchFields,
	type ListMeta,
	type RowValue,
} from "./defaults";
import { readListMemory, recallRows, rememberRows, useRememberedPageSize, writeListMemory } from "./pageState";
import { listStatusTheme, type StatusTheme } from "@/statusTheme";
import { isSwitchCell, resolveCell, type CellView } from "./cells";
import { completeFilters, queryFromAddress } from "./query";
import { partsFor } from "./rowParts";
import { cellSeenClass, isUnseen, seenColumn } from "./seen";
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
	/** What the table draws: `columns` as the page's scripts left them on `page.columns`. */
	shownColumns: ComputedRef<ListColumn[]>;
	/** The page's row actions, as its scripts left them. */
	rowActions: ComputedRef<ListRowAction[]>;
	/** The field a column shows, a standard one such as `creation` included. */
	fieldOf: (fieldname: string) => RawMetaField | undefined;
	/** What a column's cell shows before its text; see `cellMark`. */
	markOf: (fieldname: string) => CellMark | undefined;
	statusThemeOf: (fieldname: string, value: unknown) => StatusTheme | null;
	/** What the column's cell keys draw for a value, or null when they name nothing for it; see `resolveCell`. */
	cellViewOf: (fieldname: string, value: unknown) => CellView | null;
	/** Whether a column draws as a switch that writes its field; see `isSwitchCell`. */
	switchOf: (fieldname: string) => boolean;
	/** Whether the person may write the field; a switch is read-only without it. */
	canWrite: (fieldname: string) => boolean;
	/** Where a Currency column's cell finds its currency in the row; see `cellCurrency`. */
	currencyOf: (fieldname: string) => RowValue | undefined;
	/** The titles the rows hold for their Link values, keyed `Target::name` as the form's `link_titles`; see `cellTitle`. */
	linkTitles: ComputedRef<Record<string, string>>;
	selection: Ref<string[]>;
	/** Kept in the history entry. */
	pageSize: Ref<number>;
	/** The filters and sort the rows belong to, as one string: the session memory's key. */
	rowsKey: () => string;
	/** The class a cell takes on a Track Seen doctype for its row's seen state; "" off the title cell or when Track Seen is off. */
	seenClassOf: (row: ListRow, fieldname: string) => string;
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

export function useListView(view: View, lists: Pick<ListPageLists, "columns" | "rowActions">): ListView {
	const { doctype } = view;
	const { meta } = useDoctypeMeta(doctype);
	const permissions = useDocPermissions(doctype);
	const listMeta = computed(() => meta.value as ListMeta | null);
	const fields = computed(() => listMeta.value?.fields ?? []);
	const rowActions = computed(() => lists.rowActions.visible());
	const cellOf = (fieldname: string) => shownItems.value.get(fieldname);

	const switchOf = (fieldname: string) =>
		isSwitchCell(cellOf(fieldname), fields.value.find((one) => one.fieldname === fieldname)?.fieldtype);

	const readable = (fieldname: string) => {
		const field = fields.value.find((one) => one.fieldname === fieldname);
		return !field || permissions.fieldAccess(field) !== "none";
	};

	const defaults = computed(() =>
		listMeta.value ? defaultColumns(listMeta.value, listScriptsOf(doctype)) : []
	);

	/** The columns the tiers resolve to: the person's, else the site's, else the app default. */
	const columns = computed<ListColumn[]>({
		get: () => {
			const stored = columnsFrom(view.settings.value.columns, fields.value, readable, listMeta.value ?? {});
			return stored.length ? stored : defaults.value;
		},
		// A rename alone, or the app default handed back unchanged, is not the person's change.
		set: (value) => {
			const stored = toStoredColumns(value);
			if (JSON.stringify(stored) !== JSON.stringify(toStoredColumns(columns.value)))
				view.update({ columns: stored });
		},
	});

	lists.columns.provideBuiltins(() =>
		columns.value.map((column) => ({ name: column.fieldname, label: column.label, width: column.width }))
	);
	const shownItems = computed(() => new Map(lists.columns.visible().map((item) => [item.name, item])));
	const shownColumns = computed(() =>
		[...shownItems.value.values()].map((item) => shownColumn(item, columns.value, fields.value))
	);

	const selection = ref<string[]>([]);
	const pageSize = useRememberedPageSize();

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
			fields: withModified(
				fetchFields(
					shownColumns.value,
					rowActionFields(rowActions.value).filter(readable),
					listMeta.value ?? {},
					readable
				),
				shownColumns.value.some((column) => switchOf(column.fieldname))
			),
			filters: filtersDict(view.filters.value),
			orderBy: serializeOrderBy(view.sort.value),
			limit: pageSize.value,
			include: partsFor(shownColumns.value.map((column) => column.fieldname)),
		};
	});

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
		const outcome = await deleteRows(rows, selection.value);
		selection.value = [];
		return outcome;
	}

	const linkTitles = computed(() => {
		const titles: Record<string, string> = {};
		for (const { fieldname } of shownColumns.value) {
			const title = cellTitle(fieldname, listMeta.value ?? {});
			if (!title) continue;
			const target = fields.value.find((one) => one.fieldname === fieldname)?.options;
			for (const row of rows.rows.value) {
				if (row[fieldname] && row[title.key]) titles[`${target}::${row[fieldname]}`] = String(row[title.key]);
			}
		}
		return titles;
	});

	const user = currentSession()?.user.name ?? null;
	const seenField = computed(() =>
		seenColumn(listMeta.value, shownColumns.value.map((column) => column.fieldname))
	);

	return {
		...rows,
		columns,
		shownColumns,
		rowActions,
		fieldOf: (fieldname) =>
			fields.value.find((one) => one.fieldname === fieldname) ??
			getFilterableFields([], doctype).find((one) => one.fieldname === fieldname),
		markOf: (fieldname) => cellMark(fieldname, listMeta.value ?? {}),
		statusThemeOf: (fieldname, value) => listStatusTheme(listMeta.value, fieldname, value),
		cellViewOf: (fieldname, value) =>
			resolveCell(
				cellOf(fieldname),
				value,
				fields.value.find((one) => one.fieldname === fieldname)?.fieldtype
			),
		switchOf,
		canWrite: (fieldname) => {
			const field = fields.value.find((one) => one.fieldname === fieldname);
			return (
				Boolean(field) &&
				!field!.read_only &&
				permissions.allowedPermlevels("write").includes(0) &&
				permissions.fieldAccess(field!) === "write"
			);
		},
		currencyOf: (fieldname) => cellCurrency(fieldname, listMeta.value ?? {}, readable),
		linkTitles,
		seenClassOf: (row, fieldname) =>
			fieldname === seenField.value ? cellSeenClass(isUnseen(row, user)) : "",
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

// A script's own column has no stored entry: it takes its field's alignment.
function shownColumn(item: ListPageColumn, columns: ListColumn[], fields: RawMetaField[]): ListColumn {
	const stored = columns.find((column) => column.fieldname === item.name);
	const fieldtype = fields.find((field) => field.fieldname === item.name)?.fieldtype;
	const column: ListColumn = stored ?? { fieldname: item.name, label: item.name, align: getColumnAlign(fieldtype ?? "Data") };
	return { ...column, label: item.label ?? column.label, width: item.width ?? column.width };
}

function withModified(fields: string[], wanted: boolean): string[] {
	return wanted ? [...new Set([...fields, "modified"])] : fields;
}

/** The object form `useList` takes; it holds one condition per field, so a second one is lost. */
export function filtersDict(filters: FilterCondition[]): Record<string, unknown> {
	const dict: Record<string, unknown> = {};
	for (const [fieldname, operator, value] of serializeFilters(completeFilters(filters))) {
		dict[fieldname] = [operator, value];
	}
	return dict;
}

/** Deletes the rows one by one, then reloads the page; what failed comes back with its message. */
export async function deleteRows(rows: ListRows, names: string[]): Promise<DeleteOutcome> {
	const outcome: DeleteOutcome = { deleted: [], failed: [] };
	for (const name of names) {
		try {
			await rows.remove(name);
			outcome.deleted.push(name);
		} catch (failure) {
			outcome.failed.push({ name, error: messageOf(failure) });
		}
	}
	rows.reload();
	return outcome;
}

function messageOf(failure: unknown): string {
	if (failure instanceof Error) return failure.message;
	return String(failure);
}
