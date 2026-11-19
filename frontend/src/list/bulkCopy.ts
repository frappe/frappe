// Copy to Clipboard: the selected rows as tab-separated text, one line per row under the column labels.
import { listDocuments } from "@framework/ui/api";
import type { ListRow } from "./useListRows";

export interface CopyColumn {
	fieldname: string;
	label: string;
}

const cell = (text: string) => text.replace(/<\/?[a-z][^>]*>/gi, "").replace(/[\t\r\n]+/g, " ");

export function selectionTsv(
	columns: CopyColumn[],
	rows: Record<string, unknown>[],
	textOf: (row: Record<string, unknown>, fieldname: string) => string
): string {
	const header = columns.map((column) => cell(column.label)).join("\t");
	const lines = rows.map((row) => columns.map((column) => cell(textOf(row, column.fieldname))).join("\t"));
	return [header, ...lines].join("\n");
}

const HIDDEN_BATCH = 100;

/** The selected rows in selection order: the loaded ones, and the hidden ones read in batches, one at a time. */
export async function withHiddenRows(
	doctype: string,
	names: string[],
	loaded: ListRow[],
	fields: string[]
): Promise<ListRow[]> {
	const read = new Map(loaded.map((row) => [row.name, row]));
	const hidden = names.filter((name) => !read.has(name));
	if (!hidden.length) return loaded;
	// The names go in the query string: a batch keeps its URL under the proxy's limit.
	for (const batch of chunked(hidden, HIDDEN_BATCH)) {
		const { data } = await listDocuments<ListRow>(doctype, {
			fields,
			filters: { name: ["in", batch] },
			limit: batch.length,
		});
		for (const row of data) read.set(row.name, row);
	}
	return names.flatMap((name) => read.get(name) ?? []);
}

function chunked<T>(items: T[], size: number): T[][] {
	return Array.from({ length: Math.ceil(items.length / size) }, (_, index) => items.slice(index * size, (index + 1) * size));
}
