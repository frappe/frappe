import { describe, expect, it } from "vitest";
import { selectionTsv } from "../bulkCopy";

describe("selectionTsv", () => {
	it("writes the column labels, then a line per row, tab separated", () => {
		const columns = [
			{ fieldname: "name", label: "ID" },
			{ fieldname: "status", label: "Status" },
		];
		const rows = [
			{ name: "T-1", status: "Open" },
			{ name: "T-2", status: "Closed" },
		];
		expect(selectionTsv(columns, rows, (row, field) => String(row[field] ?? ""))).toBe("ID\tStatus\nT-1\tOpen\nT-2\tClosed");
	});

	it("strips markup and keeps a tab or newline in a value from breaking the grid", () => {
		const out = selectionTsv([{ fieldname: "d", label: "D" }], [{ d: "<b>a</b>\tb\nc" }], (row) => String(row.d));
		expect(out).toBe("D\na b c");
	});

	it("keeps a plain less-than sign", () => {
		const out = selectionTsv([{ fieldname: "d", label: "D" }], [{ d: "5 < 6 and 7 > 3" }], (row) => String(row.d));
		expect(out).toBe("D\n5 < 6 and 7 > 3");
	});
});
