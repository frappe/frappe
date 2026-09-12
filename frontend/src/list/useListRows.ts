// The rows and the total for one query: frappe-ui's `useList` per fetched page, `get_count` for
// the total. A changed query is a new list. The pages are a buffer; the page size and Load More
// decide how much of it shows, and only rows past its end are fetched.
import { call, useList, type Filters, type OrderBy } from "frappe-ui";
import {
	computed,
	effectScope,
	onScopeDispose,
	ref,
	shallowRef,
	watch,
	type ComputedRef,
	type EffectScope,
} from "vue";

export type ListRow = { name: string } & Record<string, unknown>;

/** Past this many rows the count is not exact and the footer reads "1000+". */
export const COUNT_BOUND = 1000;
const QUERY_DEBOUNCE_MS = 300;

export interface RowsQuery {
	/** Names the filters and sort; the loaded rows carry it, so a memory is written under it. */
	key: string;
	fields: string[];
	filters: Record<string, unknown>;
	orderBy: string;
	limit: number;
	/** Rows to show on the first load, when an earlier visit showed more than one page. */
	restore?: number;
}

export interface ListRows {
	rows: ComputedRef<ListRow[]>;
	/** True until the first page of a query lands. */
	loading: ComputedRef<boolean>;
	error: ComputedRef<Error | null>;
	rowCount: ComputedRef<number>;
	totalCount: ComputedRef<number>;
	/** True when the total hit the bound or its query timed out. */
	totalCapped: ComputedRef<boolean>;
	/** False until the count has answered; the footer shows a skeleton meanwhile. */
	hasCounts: ComputedRef<boolean>;
	hasNextPage: ComputedRef<boolean>;
	/** How many rows the page asked to show; the rows fall short when the query has fewer. */
	shown: ComputedRef<number>;
	/** Shows exactly `size` rows: a chosen page size, even the one already chosen after a Load More. */
	show(size: number): void;
	/** The `key` of the query the rows belong to, which trails the state while a change waits. */
	loadedKey: ComputedRef<string | null>;
	next: () => void;
	/** Refetches the query and shows as many rows as before. */
	reload: () => void;
	remove: (name: string) => Promise<unknown>;
}

type ListHandle = ReturnType<typeof useList<ListRow>>;

export function useListRows(doctype: string, query: () => RowsQuery | null): ListRows {
	const pages = shallowRef<ListHandle[]>([]);
	const shown = ref(0);
	const loadedKey = ref<string | null>(null);
	const total = ref<number | null>(null);
	const counted = ref(false);
	let scope: EffectScope | null = null;
	let generation = 0;
	let timer = 0;

	const loaded = computed(() => pages.value.flatMap((page) => page.data ?? []));
	const rows = computed(() => loaded.value.slice(0, shown.value));
	const rowCount = computed(() => rows.value.length);
	const firstPage = computed(() => pages.value[0] ?? null);
	const lastPage = computed(() => pages.value[pages.value.length - 1] ?? null);
	const inFlight = computed(() => lastPage.value != null && lastPage.value.data == null);
	const error = computed(
		() => (pages.value.find((page) => page.error)?.error as Error | null) ?? null
	);
	const hasNextPage = computed(
		() => loaded.value.length > shown.value || (lastPage.value?.hasNextPage ?? false)
	);

	// The first query runs at once; a typed filter changes it per keystroke, so the rest wait.
	watch(
		queryKey,
		(key, previous) => {
			clearTimeout(timer);
			if (!key) return;
			if (previous === undefined) return reload(query()!.restore);
			timer = window.setTimeout(() => reload(query()!.limit), QUERY_DEBOUNCE_MS);
		},
		{ immediate: true }
	);

	// A page size is not part of the query: it is how many rows show, and a bigger one fetches
	// only the rows still missing. While a page is in flight the offset is not known yet, so
	// the list starts over instead.
	watch(
		() => query()?.limit,
		(size, previous) => {
			if (size == null || previous == null || !lastPage.value) return;
			if (inFlight.value) return reload();
			show(size);
		}
	);

	onScopeDispose(() => {
		clearTimeout(timer);
		scope?.stop();
	});

	/** Undefined while there is no query yet, so the first real one still counts as the first. */
	function queryKey(): string | undefined {
		const current = query();
		if (!current) return undefined;
		const { fields, filters, orderBy } = current;
		return JSON.stringify({ fields, filters, orderBy });
	}

	function reload(target = shown.value) {
		const current = query();
		scope?.stop();
		pages.value = [];
		shown.value = 0;
		loadedKey.value = current?.key ?? null;
		if (!current) return;
		scope = effectScope();
		show(Math.max(target ?? 0, current.limit));
		void count(current.filters);
	}

	/** Shows `target` rows: from the buffer where it reaches, fetched past its end. */
	function show(target: number) {
		shown.value = target;
		const missing = target - loaded.value.length;
		if (missing <= 0 || lastPage.value?.hasNextPage === false) return;
		const page = scope!.run(() => createList(doctype, query()!, loaded.value.length, missing));
		if (page) pages.value = [...pages.value, page];
	}

	// A page still in flight has no data yet; a second Load More then would start at a stale offset.
	function next() {
		const current = query();
		if (!current || !lastPage.value || inFlight.value) return;
		show(rowCount.value + current.limit);
	}

	// `limit` caps the count and puts a one-second cap on its query; a timeout answers null.
	async function count(filters: Record<string, unknown>) {
		const mine = ++generation;
		counted.value = false;
		total.value = null;
		const params = { doctype, filters, limit: COUNT_BOUND + 1 };
		const answer = await call<number | null>("frappe.client.get_count", params)
			.then((value) => value ?? COUNT_BOUND + 1)
			.catch(() => null);
		if (mine !== generation) return;
		total.value = answer;
		counted.value = true;
	}

	// A failed count shows the rows as a floor; Load More follows the list's own next page.
	const totalCapped = computed(() =>
		total.value == null ? hasNextPage.value : total.value > COUNT_BOUND
	);

	return {
		rows,
		loading: computed(
			() => !firstPage.value || (firstPage.value.data == null && !error.value)
		),
		error,
		rowCount,
		totalCount: computed(() =>
			total.value == null ? rowCount.value : Math.min(total.value, COUNT_BOUND)
		),
		totalCapped,
		hasCounts: computed(() => counted.value),
		hasNextPage,
		shown: computed(() => shown.value),
		loadedKey: computed(() => loadedKey.value),
		show: (size) => {
			if (!lastPage.value) return;
			if (inFlight.value) return reload(size);
			show(size);
		},
		next,
		reload: () => reload(),
		remove: (name) => firstPage.value!.delete.submit({ name }),
	};
}

/** One page, fetched once: `refetch` is off, so a delete never refetches from a stale offset. */
function createList(doctype: string, query: RowsQuery, start: number, limit: number): ListHandle {
	return useList<ListRow>({
		doctype,
		fields: query.fields,
		filters: query.filters as Filters,
		orderBy: query.orderBy as OrderBy,
		start,
		limit,
		refetch: false,
	});
}
