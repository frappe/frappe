// What a visit keeps in its history entry: the page size and the scroll offset, so Back lands
// where the reader left. What the session keeps per doctype: how many rows were showing and the
// scroll offset, so a return from a record by any route, a breadcrumb too, lands there again.

export interface ListMemory {
	pageSize?: number;
	scrollTop?: number;
}

export function readListMemory(): ListMemory {
	const list = (history.state as { list?: unknown } | null)?.list;
	return typeof list === "object" && list ? (list as ListMemory) : {};
}

/** Spread over the current state: vue-router keeps its own keys there. */
export function writeListMemory(patch: ListMemory): void {
	const list = { ...readListMemory(), ...patch };
	history.replaceState({ ...history.state, list }, "");
}

export interface RowsMemory {
	/** The filters and sort the rows belonged to; a different query starts fresh. */
	query: string;
	pageSize: number;
	shown: number;
	scrollTop?: number;
}

const rowsByDoctype = new Map<string, RowsMemory>();

/** Patches the memory for the same query, so a Load More keeps the offset; a new query replaces it. */
export function rememberRows(doctype: string, memory: Omit<RowsMemory, "scrollTop">): void {
	rowsByDoctype.set(doctype, { ...recallRows(doctype, memory.query), ...memory });
}

export function rememberScroll(doctype: string, query: string, scrollTop: number): void {
	const memory = recallRows(doctype, query);
	if (memory) rowsByDoctype.set(doctype, { ...memory, scrollTop });
}

export function recallRows(doctype: string, query: string): RowsMemory | undefined {
	const memory = rowsByDoctype.get(doctype);
	return memory?.query === query ? memory : undefined;
}

export function forgetRows(doctype: string): void {
	rowsByDoctype.delete(doctype);
}
