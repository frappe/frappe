// The rows and the total for one query: one list read per fetched page, the first carrying the
// count. A changed query is a new list. The pages are a buffer; the page size and Load More
// decide how much of it shows, and only rows past its end are fetched.
import { countDocuments, deleteDocument, listDocuments } from "@framework/ui/api";
import {
	computed,
	onScopeDispose,
	reactive,
	ref,
	shallowRef,
	watch,
	type ComputedRef,
} from "vue";

export type ListRow = { name: string } & Record<string, unknown>;

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
	/** True when the total stopped at the server's cap, or is unknown and a next page remains. */
	totalCapped: ComputedRef<boolean>;
	/** True when the server gave up counting; the footer reads "many". */
	totalUnknown: ComputedRef<boolean>;
	/** False until the count has answered; the footer shows a skeleton meanwhile, also after an error. */
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
	/** Asks for the exact total after a capped one. */
	countExact: () => Promise<void>;
	remove: (name: string) => Promise<unknown>;
}

interface Page {
	data: ListRow[] | null;
	error: Error | null;
	hasNextPage: boolean;
}

interface Total {
	count: number | null;
	capped: boolean;
	answered: boolean;
}

export function useListRows(doctype: string, query: () => RowsQuery | null): ListRows {
	const pages = shallowRef<Page[]>([]);
	const shown = ref(0);
	const loadedKey = ref<string | null>(null);
	const total = ref<Total>({ count: null, capped: false, answered: false });
	let generation = 0;
	let timer = 0;

	const loaded = computed(() => pages.value.flatMap((page) => page.data ?? []));
	const rows = computed(() => loaded.value.slice(0, shown.value));
	const rowCount = computed(() => rows.value.length);
	const firstPage = computed(() => pages.value[0] ?? null);
	const lastPage = computed(() => pages.value[pages.value.length - 1] ?? null);
	const inFlight = computed(() => lastPage.value != null && lastPage.value.data == null);
	const error = computed(() => pages.value.find((page) => page.error)?.error ?? null);
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

	onScopeDispose(() => clearTimeout(timer));

	/** Undefined while there is no query yet, so the first real one still counts as the first. */
	function queryKey(): string | undefined {
		const current = query();
		if (!current) return undefined;
		const { fields, filters, orderBy } = current;
		return JSON.stringify({ fields, filters, orderBy });
	}

	function reload(target = shown.value) {
		const current = query();
		generation++;
		pages.value = [];
		shown.value = 0;
		total.value = { count: null, capped: false, answered: false };
		loadedKey.value = current?.key ?? null;
		if (!current) return;
		show(Math.max(target ?? 0, current.limit));
	}

	/** Shows `target` rows: from the buffer where it reaches, fetched past its end. */
	function show(target: number) {
		shown.value = target;
		const missing = target - loaded.value.length;
		if (missing <= 0 || lastPage.value?.hasNextPage === false) return;
		const page = reactive<Page>({ data: null, error: null, hasNextPage: false });
		pages.value = [...pages.value, page];
		void fetchPage(page, query()!, loaded.value.length, missing);
	}

	// A page still in flight has no data yet; a second Load More then would start at a stale offset.
	function next() {
		const current = query();
		if (!current || !lastPage.value || inFlight.value) return;
		show(rowCount.value + current.limit);
	}

	// The first page of a query carries the count; a page from an earlier query lands nowhere.
	async function fetchPage(page: Page, current: RowsQuery, start: number, limit: number) {
		const mine = generation;
		const first = start === 0;
		try {
			const answer = await listDocuments<ListRow>(
				doctype,
				{
					fields: current.fields,
					filters: current.filters,
					order_by: current.orderBy,
					start,
					limit,
				},
				{ include: first ? ["count"] : undefined }
			);
			if (mine !== generation) return;
			page.hasNextPage = answer.has_next_page;
			page.data = answer.data;
			if (first) {
				const capped = Boolean(answer.count_capped);
				total.value = { count: answer.count ?? null, capped, answered: true };
			}
		} catch (failure) {
			if (mine !== generation) return;
			page.error = failure as Error;
		}
	}

	async function countExact() {
		const current = query();
		if (!current) return;
		const mine = generation;
		const { data } = await countDocuments(doctype, { filters: current.filters }).catch(() => ({
			data: null,
		}));
		if (mine !== generation || data == null) return;
		total.value = { count: data, capped: false, answered: true };
	}

	// An unknown total shows the rows as a floor; Load More follows the list's own next page.
	const totalCapped = computed(() =>
		total.value.count == null ? hasNextPage.value : total.value.capped
	);

	return {
		rows,
		loading: computed(
			() => !firstPage.value || (firstPage.value.data == null && !error.value)
		),
		error,
		rowCount,
		totalCount: computed(() => total.value.count ?? rowCount.value),
		totalCapped,
		totalUnknown: computed(() => total.value.answered && total.value.count == null),
		hasCounts: computed(() => total.value.answered),
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
		countExact,
		remove: (name) => deleteDocument(doctype, name),
	};
}
