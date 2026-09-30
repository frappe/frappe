// The rows and the total for one query, painted from the shared cache when it holds the query.
// The pages are a buffer: the page size and Load More decide how much shows.
import {
	countDocuments,
	deleteDocument,
	isApiError,
	listDocuments,
	type ListEnvelope,
	type ListQuery,
} from "@framework/ui/api";
import { readCachedList, readCachedRows } from "@framework/ui/cache";
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
	// The generation whose background read is out; a Load More meanwhile only raises `shown`.
	let refreshing = -1;
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
			if (previous === undefined) return reload();
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
		loadedKey.value = current?.key ?? null;
		if (current && paintCached(current, target)) return void refresh(current);
		pages.value = [];
		shown.value = 0;
		total.value = { count: null, capped: false, answered: false };
		if (current) show(Math.max(target, current.limit));
	}

	/** False when the cache holds no list for the query; otherwise shows every name it lists. */
	function paintCached(current: RowsQuery, target: number): boolean {
		const entry = readCachedList(doctype, listQuery(current));
		const cached = entry && readCachedRows(doctype, listQuery(current));
		if (!entry || !cached) return false;
		pages.value = [landedPage(cached as ListRow[], entry.hasNextPage)];
		const { count, countCapped } = entry;
		total.value = { count: count ?? null, capped: countCapped, answered: count !== undefined };
		shown.value = Math.max(target, entry.names.length, current.limit);
		return true;
	}

	/** Reads every shown row again and swaps rows and count in one step; a failure keeps them. */
	async function refresh(current: RowsQuery) {
		const mine = (refreshing = generation);
		const limit = shown.value;
		const outcome = await listDocuments<ListRow>(
			doctype,
			{ ...listQuery(current), start: 0, limit },
			{ include: ["count"] }
		).catch((failure: Error) => failure);
		if (mine !== generation) return;
		refreshing = -1;
		if (isLostAccess(outcome)) return showError(outcome);
		if (!(outcome instanceof Error)) {
			pages.value = [landedPage(outcome.data, outcome.has_next_page)];
			total.value = totalOf(outcome);
		}
		if (shown.value > limit) show(shown.value);
	}

	/** As on a cold load: the error, and no count. */
	function showError(failure: Error) {
		pages.value = [{ data: null, error: failure, hasNextPage: false }];
		total.value = { count: null, capped: false, answered: false };
	}

	/** Shows `target` rows: from the buffer where it reaches, fetched past its end. */
	function show(target: number) {
		shown.value = target;
		if (refreshing === generation) return;
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
				{ ...listQuery(current), start, limit },
				{ include: first ? ["count"] : undefined }
			);
			if (mine !== generation) return;
			page.hasNextPage = answer.has_next_page;
			page.data = answer.data;
			if (first) total.value = totalOf(answer);
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

/** The read's filters, sort and fields: the shared cache keys the list by them. */
function listQuery(current: RowsQuery): ListQuery {
	return { fields: current.fields, filters: current.filters, order_by: current.orderBy };
}

function landedPage(data: ListRow[], hasNextPage: boolean): Page {
	return reactive<Page>({ data, error: null, hasNextPage });
}

function totalOf(answer: ListEnvelope<ListRow>): Total {
	return { count: answer.count ?? null, capped: Boolean(answer.count_capped), answered: true };
}

function isLostAccess(failure: unknown): failure is Error {
	return isApiError(failure) && (failure.status === 403 || failure.status === 404);
}
