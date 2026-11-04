// The Cards type's rows area: the title and body fields from the view's settings, and the rows the
// view's filters and sort read, with the page size and the delete.
import { listDocuments } from "@framework/ui/api";
import { serializeOrderBy } from "@framework/ui/SortBy";
import { useDocPermissions } from "@framework/ui/useDocPermissions";
import { useDoctypeMeta } from "@framework/ui/useDoctypeMeta";
import { computed, inject, reactive, watch, type ComputedRef, type Ref } from "vue";
import type { RouteLocationRaw } from "vue-router";
import type { Boot } from "@/boot";
import { listHandlersFor } from "@/contributions/registry";
import type { RowAction } from "@/contributions/types";
import { contributedRowActions, type ListMeta } from "@/list/defaults";
import { useRememberedPageSize } from "@/list/pageState";
import { queryFromAddress } from "@/list/query";
import { deleteRows, filtersDict, type DeleteOutcome } from "@/list/useListView";
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
	/** The row actions the apps contributed for this doctype. */
	rowActions: RowAction[];
	/** Who the rows' owners are, as far as they have been read. */
	people: Record<string, Person>;
	pageSize: Ref<number>;
	cardLink: (row: ListRow) => RouteLocationRaw;
	deleteOne: (name: string) => Promise<DeleteOutcome>;
}

export function useCardsView(view: View): CardsView {
	const { doctype } = view;
	forgetPeopleOf(inject<Boot>("boot")!.session.user.name);
	const { meta } = useDoctypeMeta(doctype);
	const permissions = useDocPermissions(doctype);
	const listMeta = computed(() => meta.value as ListMeta | null);
	const contributed = listHandlersFor(doctype).map(({ handlers }) => handlers);
	const rowActions = contributedRowActions(contributed);

	const readable = (fieldname: string) => {
		const field = listMeta.value?.fields?.find((one) => one.fieldname === fieldname);
		return !field || permissions.fieldAccess(field) !== "none";
	};

	const fields = computed(() => cardFields(listMeta.value ?? {}, view.settings.value, readable));
	const pageSize = useRememberedPageSize();

	const rows = useListRows(doctype, () => {
		if (!view.seeded.value || !listMeta.value) return null;
		const wanted = new Set([
			"name",
			fields.value.title,
			...(fields.value.body ? [fields.value.body] : []),
			"owner",
			"modified",
			...rowActions.flatMap((action) => action.fields.filter(readable)),
		]);
		return {
			key: JSON.stringify(queryFromAddress({ filters: view.filters.value, sort: view.sort.value })),
			fields: [...wanted],
			filters: filtersDict(view.filters.value),
			orderBy: serializeOrderBy(view.sort.value),
			limit: pageSize.value,
		};
	});

	watch(rows.rows, (current) => readPeople(current.map((row) => String(row.owner ?? ""))), { immediate: true });

	const deleteOne = (name: string) => deleteRows(rows, [name]);

	return { ...rows, fields, rowActions, people, pageSize, cardLink: (row) => routeFor(doctype, row.name), deleteOne };
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
