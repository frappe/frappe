// The page size and scroll offset, kept in the history entry for Back and per doctype for a
// return by any other route. The rows, and how many showed, are the shared cache's list entry.
import { keepInHistory } from "@framework/ui/utils/scrollLanding";

export interface ListMemory {
	pageSize?: number;
	scrollTop?: number;
}

export function readListMemory(): ListMemory {
	const list = (history.state as { list?: unknown } | null)?.list;
	return typeof list === "object" && list ? (list as ListMemory) : {};
}

export function writeListMemory(patch: ListMemory): void {
	keepInHistory("list", { ...readListMemory(), ...patch });
}

export interface RowsMemory {
	/** The filters and sort the offset belongs to; a different query starts at the top. */
	query: string;
	pageSize: number;
	scrollTop?: number;
}

const rowsByDoctype = new Map<string, RowsMemory>();

/** Patches the memory for the same query, keeping its offset; a new query replaces it. */
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
