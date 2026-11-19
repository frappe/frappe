import type { BulkPrintBody } from "@framework/ui/api";

// What the bulk Print dialog offers, and the request body its choices make.
export const PAGE_SIZES = [
	...Array.from({ length: 10 }, (_, size) => `A${size}`),
	...Array.from({ length: 11 }, (_, size) => `B${size}`),
	"C5E",
	"Comm10E",
	"DLE",
	"Executive",
	"Folio",
	"Ledger",
	"Legal",
	"Letter",
	"Tabloid",
];

interface PrintFormatRow {
	name?: unknown;
	print_format_type?: unknown;
	print_format_for?: unknown;
	raw_printing?: unknown;
}

/** Drops the JS, report and raw-printing formats: none of them prints to a PDF page. */
export function printableFormats(rows: PrintFormatRow[]): string[] {
	return rows
		.filter((row) => row.print_format_type !== "JS" && row.print_format_for !== "Report" && !row.raw_printing)
		.map((row) => String(row.name));
}

export const DEFAULT = "";
export const NO_LETTERHEAD = "\u0000none";

export interface PrintChoices {
	printFormat: string;
	letterhead: string;
	pageSize: string;
}

/** A default choice is left out, so the server applies the doctype's and Print Settings' own. */
export function printBody(scope: BulkPrintBody, choices: PrintChoices): BulkPrintBody {
	const { printFormat, letterhead, pageSize } = choices;
	return {
		...scope,
		print_format: printFormat || undefined,
		letterhead: letterhead === NO_LETTERHEAD ? undefined : letterhead || undefined,
		no_letterhead: letterhead === NO_LETTERHEAD || undefined,
		page_size: pageSize || undefined,
	};
}
