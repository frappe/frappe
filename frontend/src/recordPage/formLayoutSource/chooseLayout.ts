import type { FormLayoutRow, LayoutTree } from "./types";

/** The first matching conditional row (rows arrive `creation asc`), else the default row, else `null`. */
export function chooseLayout(
	rows: FormLayoutRow[],
	doc: Record<string, any>
): LayoutTree | null {
	const matches = rows.filter(
		(row) => row.condition && matchesCondition(row.condition, doc)
	);
	if (matches.length > 1 && import.meta.env?.DEV) {
		console.warn(
			`[form-layout] ${matches.length} conditional layouts match; using the earliest.`
		);
	}
	const chosen = matches[0] ?? rows.find((row) => !row.condition);
	return chosen?.layout ?? null;
}

/**
 * The `depends_on` dialect: an optional `eval:` prefix, a bare fieldname, or a JS expression
 * over `doc`. An expression that throws matches nothing, so a broken condition cannot steal the layout.
 */
export function matchesCondition(
	condition: string,
	doc: Record<string, any>
): boolean {
	const expression = (
		condition.startsWith("eval:") ? condition.slice(5) : condition
	).trim();
	if (!expression) return false;
	if (/^[A-Za-z_$][\w$]*$/.test(expression)) {
		const value = doc?.[expression];
		return Array.isArray(value) ? value.length > 0 : Boolean(value);
	}
	try {
		return Boolean(new Function("doc", `return (${expression})`)(doc));
	} catch (error) {
		if (import.meta.env?.DEV)
			console.warn(`[form-layout] condition threw: ${condition}`, error);
		return false;
	}
}
