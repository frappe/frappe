import { describe, expect, it } from "vitest";
import { insertToken, nextName, patternTokens, seriesPrefixes } from "../namingPattern";

const today = new Date(2026, 10, 13);
const labelOf = (fieldname: string) => ({ customer: "Customer" })[fieldname] ?? fieldname;
const shown = (pattern: string, counters: Record<string, number> = {}) =>
	nextName(pattern, counters, labelOf, today)
		.map((part) => (part.gray ? `[${part.text}]` : part.text))
		.join("");

describe("a naming pattern's next name", () => {
	it("counts a dot series under its resolved prefix", () => {
		expect(seriesPrefixes("TN-.YYYY.-.####", today)).toEqual(["TN-2026-"]);
		expect(shown("TN-.YYYY.-.####", { "TN-2026-": 41 })).toBe("TN-2026-0042");
	});

	it("appends five digits to a series without a counter", () => {
		expect(shown("NOTE-")).toBe("NOTE-00001");
	});

	it("counts a braced counter of a format pattern under the empty prefix, as frappe does", () => {
		expect(seriesPrefixes("format:TN-{MM}{DD}-{#####}", today)).toEqual([""]);
		expect(shown("format:TN-{MM}{DD}-{#####}", { "": 6 })).toBe("TN-1113-00007");
	});

	it("resolves braced tokens in a dot series first and counts under the prefix they make, as frappe's Expression does", () => {
		expect(seriesPrefixes("TN-{MM}-.#####", today)).toEqual(["TN-11-"]);
		expect(shown("TN-{MM}-.#####", { "TN-11-": 4 })).toBe("TN-11-00005");
		expect(seriesPrefixes("{customer}-.###", today)).toEqual([]);
	});

	it("shows a field's label in gray, and a counter whose prefix holds a field in gray", () => {
		expect(seriesPrefixes("format:{customer}-.###", today)).toEqual([]);
		expect(shown("format:{customer}-.###")).toBe("[<Customer>]-[###]");
	});

	it("resolves the day of year and a week that runs on across the year's edges, as frappe does", () => {
		expect(shown("TN-.JJJ.-.WW.-.###")).toBe("TN-317-46-001");
		expect(nextName("W.WW.", {}, labelOf, new Date(2027, 0, 1))[1].text).toBe("00");
		expect(nextName("W.WW.", {}, labelOf, new Date(2025, 11, 31))[1].text).toBe("53");
	});

	it("shows a timestamp in gray, with no counter to look up", () => {
		expect(seriesPrefixes("TN-.timestamp.-.###", today)).toEqual([]);
		expect(shown("TN-.timestamp.-.###")).toBe("TN-[<timestamp>]-[###]");
	});

	it("inserts a chip's token at the caret", () => {
		expect(patternTokens(false)).toEqual(["{YYYY}", "{MM}", "{DD}", "{#####}"]);
		expect(insertToken("TN-", "{YYYY}", 3)).toEqual({ pattern: "TN-{YYYY}", caret: 9 });
		expect(insertToken("TN--{#####}", "{MM}", 3)).toEqual({ pattern: "TN-{MM}-{#####}", caret: 7 });
	});

	it("gives a dotted pattern dotted chips, so its counter counts under the typed prefix", () => {
		expect(patternTokens(true, "customer")).toEqual([".YYYY.", ".MM.", ".DD.", ".#####.", ".{customer}."]);
		const pattern = insertToken("ST-.YYYY.-A", ".#####.", 10).pattern;
		expect(pattern).toBe("ST-.YYYY.-.#####.A");
		expect(seriesPrefixes(pattern, today)).toEqual(["ST-2026-"]);
		expect(nextName(pattern, {}, String, today).map((part) => part.text).join("")).toBe("ST-2026-00001A");
	});
});
