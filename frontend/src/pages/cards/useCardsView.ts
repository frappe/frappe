// The Cards type's rows area: the title and body fields from the view's settings, and the rows the
// view's filters and sort read, with the page size and the delete.
import { listDocuments } from "@framework/ui/api";
import { serializeOrderBy } from "@framework/ui/SortBy";
import { useDocPermissions } from "@framework/ui/useDocPermissions";
import { useDoctypeMeta } from "@framework/ui/useDoctypeMeta";
import { currentSession } from "@framework/ui/useSession";
import { computed, inject, reactive, ref, watch, type ComputedRef, type Ref } from "vue";
import type { RouteLocationRaw } from "vue-router";
import type { Boot } from "@/boot";
import type { ListMeta } from "@/list/defaults";
import type { ListPageLists } from "@/listPage/createListPage";
import type { ListRowAction } from "@/listPage/types";
import { rowActionFields } from "@/listPage/types";
import { useRememberedPageSize } from "@/list/pageState";
import { queryFromAddress } from "@/list/query";
import { cardSeenClass, isUnseen } from "@/list/seen";
import { deleteRow, deleteRows, filtersDict, filtersFit, type DeleteOutcome } from "@/list/useListView";
import { useBulkScope, type BulkScope } from "@/list/useBulkScope";
import { useListRows, type ListRow, type ListRows } from "@/list/useListRows";
import type { View } from "@/list/view";
import { routeFor } from "@/router/routeFor";
import { cardFields, type CardFields } from "./cardFields";

export interface Person {
	name: string;
	image: string | null;
}

// A person's name and photo by user id, read once per session; `owner` is no Link the list can follow.
// What one user may read is not what the next may, so another session user starts it empty.
const people = reactive<Record<string, Person>>({});
const asked = new Set<string>();
let askedBy = "";

function forgetPeopleOf(user: string) {
	if (askedBy === user) return;
	askedBy = user;
	asked.clear();
	for (const id of Object.keys(people)) delete people[id];
}

export interface CardsView extends ListRows {
	fields: ComputedRef<CardFields>;
	/** The page's row actions, as its scripts left them. */
	rowActions: ComputedRef<ListRowAction[]>;
	/** Who the rows' owners are, as far as they have been read. */
	people: Record<string, Person>;
	pageSize: Ref<number>;
	/** The names of the selected cards, in the order they were picked. */
	selection: Ref<string[]>;
	scope: BulkScope;
	cardLink: (row: ListRow) => RouteLocationRaw;
	/** The title's class for the row's seen state; "" when the doctype does not track seen. */
	titleClassOf: (row: ListRow) => string;
	deleteOne: (name: string) => Promise<DeleteOutcome>;
	/** Deletes the selection in one bulk request; the page confirms first. */
	deleteSelection: () => Promise<DeleteOutcome>;
}

export function useCardsView(view: View, lists: Pick<ListPageLists, "rowActions">): CardsView {
	const { doctype } = view;
	forgetPeopleOf(inject<Boot>("boot")!.session.user.name);
	const { meta } = useDoctypeMeta(doctype);
	const permissions = useDocPermissions(doctype);
	const listMeta = computed(() => meta.value as ListMeta | null);
	const rowActions = computed(() => lists.rowActions.visible());

	const readable = (fieldname: string) => {
		const field = listMeta.value?.fields?.find((one) => one.fieldname === fieldname);
		return !field || permissions.fieldAccess(field) !== "none";
	};

	const fields = computed(() => cardFields(listMeta.value ?? {}, view.settings.value, readable));
	const pageSize = useRememberedPageSize();

	const stateKey = () => JSON.stringify(queryFromAddress({ filters: view.filters.value, sort: view.sort.value }));
	const rows = useListRows(doctype, () => {
		if (!view.seeded.value || !listMeta.value) return null;
		const wanted = new Set([
			"name",
			fields.value.title,
			...(fields.value.body ? [fields.value.body] : []),
			"owner",
			"modified",
			...(listMeta.value.track_seen ? ["_seen"] : []),
			...rowActionFields(rowActions.value).filter(readable),
		]);
		return {
			key: stateKey(),
			fields: [...wanted],
			filters: filtersDict(view.filters.value),
			orderBy: serializeOrderBy(view.sort.value),
			limit: pageSize.value,
			// The bar's Favourite reads the stars, as the list view's does.
			include: ["favourites"],
		};
	});

	watch(rows.rows, (current) => readPeople(current.map((row) => String(row.owner ?? ""))), { immediate: true });

	const deleteOne = (name: string) => deleteRow(rows, name);

	const selection = ref<string[]>([]);
	const scope = useBulkScope({
		selection,
		rows: () => rows.rows.value,
		filters: () => filtersDict(view.filters.value),
		rowsQuery: () => rows.loadedKey.value,
		hasNextPage: () => rows.hasNextPage.value,
		totalCount: () => rows.totalCount.value,
		totalApprox: () => rows.totalCapped.value,
		exact: () =>
			rows.loadedKey.value === stateKey() &&
			rows.hasCounts.value &&
			!rows.totalUnknown.value &&
			filtersFit(view.filters.value),
	});

	async function deleteSelection(): Promise<DeleteOutcome> {
		const outcome = await deleteRows(doctype, rows, scope.selected(), (names) => {
			scope.clear();
			selection.value = names;
		});
		scope.clear();
		return outcome;
	}

	const user = currentSession()?.user.name ?? null;
	const titleClassOf = (row: ListRow) =>
		listMeta.value?.track_seen ? cardSeenClass(isUnseen(row, user)) : "";

	return {
		...rows,
		fields,
		rowActions,
		people,
		pageSize,
		selection,
		scope,
		cardLink: (row) => routeFor(doctype, row.name),
		titleClassOf,
		deleteOne,
		deleteSelection,
	};
}

async function readPeople(ids: string[]) {
	const unseen = [...new Set(ids)].filter((id) => id && !asked.has(id));
	if (!unseen.length) return;
	for (const id of unseen) asked.add(id);
	try {
		const { data } = await listDocuments<{ name: string; full_name: string; user_image: string | null }>("User", {
			fields: ["name", "full_name", "user_image"],
			filters: { name: ["in", unseen] },
			limit: unseen.length,
		});
		for (const user of data) people[user.name] = { name: user.full_name || user.name, image: user.user_image };
	} catch {
		// The email stands in for the name.
	}
}
