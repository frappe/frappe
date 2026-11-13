import { describe, expect, it } from "vitest";
import { insertToken, nextName, seriesPrefixes, TOKENS } from "../namingPattern";

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
		expect(TOKENS).toContain("{#####}");
		expect(insertToken("TN-", "{YYYY}", 3)).toEqual({ pattern: "TN-{YYYY}", caret: 9 });
		expect(insertToken("TN--{#####}", "{MM}", 3)).toEqual({ pattern: "TN-{MM}-{#####}", caret: 7 });
	});
});
