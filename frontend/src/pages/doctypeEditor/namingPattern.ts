// A naming pattern's next name, as `frappe/model/naming.py` builds it (`TN-.YYYY.-.####` or
// `format:TN-{MM}-{#####}`). Each counter is kept in `tabSeries` under the text resolved before it.

/** The chips "By pattern" inserts; a field chip inserts `{fieldname}`. */
export const TOKENS = ["{YYYY}", "{MM}", "{DD}", "{#####}"];

export interface NamePart {
	text: string;
	/** A placeholder: a field's value, or a counter whose key holds one. */
	gray?: boolean;
}

/** A counter's key is `null` when a field's value is part of it. */
type Segment = { text: string } | { field: string } | { digits: number; key: string | null };

/** The `tabSeries` keys the pattern counts under, for `get_series_counters`. */
export function seriesPrefixes(pattern: string, today: Date): string[] {
	return segments(pattern, today).flatMap((segment) =>
		"digits" in segment && segment.key !== null ? [segment.key] : [],
	);
}

/** The name the next record gets; `counters` holds each key's last number. */
export function nextName(
	pattern: string,
	counters: Record<string, number>,
	labelOf: (fieldname: string) => string,
	today: Date,
): NamePart[] {
	return segments(pattern, today).map((segment) => {
		if ("text" in segment) return { text: segment.text };
		if ("field" in segment) return { text: `<${labelOf(segment.field)}>`, gray: true };
		if (segment.key === null) return { text: "#".repeat(segment.digits), gray: true };
		return { text: String((counters[segment.key] ?? 0) + 1).padStart(segment.digits, "0") };
	});
}

export function insertToken(pattern: string, token: string, caret: number): { pattern: string; caret: number } {
	return { pattern: pattern.slice(0, caret) + token + pattern.slice(caret), caret: caret + token.length };
}

function segments(pattern: string, today: Date): Segment[] {
	if (pattern.startsWith("format:")) return bracedSegments(pattern.slice("format:".length), today, false);
	return bracedSegments(pattern.includes("#") ? pattern : `${pattern}.#####`, today, true);
}

/** Each braced token resolves alone; the rest then parses as a dot series, a format pattern's only where it counts. */
function bracedSegments(body: string, today: Date, dotted: boolean): Segment[] {
	const normalised = body.replace(/(?<!\.)(-\.#+)/g, ".$1");
	const items: (Segment | string)[] = [];
	for (const piece of normalised.split(/(\{[^}]*\})/)) {
		if (!piece) continue;
		if (piece.startsWith("{")) items.push(...new SeriesParser(today, true).parse([piece.slice(1, -1)]));
		else items.push(...(dotted || piece.includes("#") ? piece.split(".") : [{ text: piece }]));
	}
	return new SeriesParser(today).parse(items);
}

class SeriesParser {
	private prefix: string | null = "";
	private counted = false;
	private found: Segment[] = [];

	constructor(
		private today: Date,
		private braced = false,
	) {}

	parse(items: (Segment | string)[]): Segment[] {
		for (const item of items) this.add(typeof item === "string" ? this.resolve(item) : item);
		return this.found;
	}

	private resolve(part: string): Segment | null {
		if (!part) return null;
		if (/^#+$/.test(part)) {
			if (this.counted) return null;
			this.counted = true;
			return { digits: part.length, key: this.prefix };
		}
		const date = this.date(part);
		if (date !== undefined) return { text: date };
		return this.braced || part === "timestamp" ? { field: part } : { text: part };
	}

	private add(segment: Segment | null) {
		if (!segment) return;
		this.found.push(segment);
		if ("field" in segment) this.prefix = null;
		else if ("text" in segment && this.prefix !== null) this.prefix += segment.text;
	}

	private date(part: string): string | undefined {
		const year = String(this.today.getFullYear());
		const pad = (value: number) => String(value).padStart(2, "0");
		return {
			YYYY: year,
			YY: year.slice(2),
			MM: pad(this.today.getMonth() + 1),
			DD: pad(this.today.getDate()),
			JJJ: String(dayOfYear(this.today)).padStart(3, "0"),
			WW: consecutiveWeek(this.today),
		}[part];
	}
}

function dayOfYear(date: Date): number {
	return utcDayOfYear(new Date(Date.UTC(date.getFullYear(), date.getMonth(), date.getDate())));
}

function utcDayOfYear(day: Date): number {
	return (day.getTime() - Date.UTC(day.getUTCFullYear(), 0, 1)) / 86_400_000 + 1;
}

/** The ISO week, except January's days of week 52/53 are "00" and December's of week 1 are "53". */
function consecutiveWeek(date: Date): string {
	const thursday = new Date(Date.UTC(date.getFullYear(), date.getMonth(), date.getDate()));
	thursday.setUTCDate(thursday.getUTCDate() + 4 - (thursday.getUTCDay() || 7));
	const week = Math.ceil(utcDayOfYear(thursday) / 7);
	if (date.getMonth() === 0 && week >= 52) return "00";
	if (date.getMonth() === 11 && week <= 1) return "53";
	return String(week).padStart(2, "0");
}
