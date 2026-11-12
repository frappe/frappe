// Copy to Clipboard: the loaded selected rows as tab-separated text, one line per row under the column labels.
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
