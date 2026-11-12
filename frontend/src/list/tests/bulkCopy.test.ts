import { beforeEach, describe, expect, it, vi } from "vitest";

const listDocuments = vi.hoisted(() => vi.fn());
vi.mock("@framework/ui/api", () => ({ listDocuments }));

import { selectionTsv, withHiddenRows } from "../bulkCopy";

beforeEach(() => listDocuments.mockReset());

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

describe("withHiddenRows", () => {
	const fields = ["name", "status"];
	const loaded = [{ name: "T-2", status: "Open" }];

	it("reads nothing when every selected row is loaded", async () => {
		expect(await withHiddenRows("ToDo", ["T-2"], loaded, fields)).toEqual(loaded);
		expect(listDocuments).not.toHaveBeenCalled();
	});

	it("reads the hidden selected rows with the list's fields and keeps the selection order", async () => {
		listDocuments.mockResolvedValue({
			data: [
				{ name: "T-1", status: "Closed" },
				{ name: "T-3", status: "Open" },
			],
		});
		const rows = await withHiddenRows("ToDo", ["T-3", "T-2", "T-9", "T-1"], loaded, fields);
		expect(listDocuments).toHaveBeenCalledWith("ToDo", {
			fields,
			filters: { name: ["in", ["T-3", "T-9", "T-1"]] },
			limit: 3,
		});
		expect(rows.map((row) => row.name)).toEqual(["T-3", "T-2", "T-1"]);
		const tsv = selectionTsv([{ fieldname: "status", label: "Status" }], rows, (row, field) => String(row[field]));
		expect(tsv).toBe("Status\nOpen\nOpen\nClosed");
	});
	it("reads many hidden rows in batches of 100, so no query string grows past the proxy's limit", async () => {
		const names = Array.from({ length: 250 }, (_, index) => `H-${index}`);
		for (const start of [0, 100, 200])
			listDocuments.mockResolvedValueOnce({ data: names.slice(start, start + 100).map((name) => ({ name })) });
		const rows = await withHiddenRows("ToDo", names, [], fields);
		expect(listDocuments.mock.calls.map(([, { limit }]) => limit)).toEqual([100, 100, 50]);
		expect(rows.map((row) => row.name)).toEqual(names);
	});

	it("reads one batch at a time", async () => {
		const names = Array.from({ length: 150 }, (_, index) => `H-${index}`);
		let release!: () => void;
		listDocuments.mockReturnValueOnce(new Promise((resolve) => (release = () => resolve({ data: [] }))));
		listDocuments.mockResolvedValueOnce({ data: [] });
		const rows = withHiddenRows("ToDo", names, [], fields);
		await Promise.resolve();
		expect(listDocuments).toHaveBeenCalledTimes(1);
		release();
		await rows;
		expect(listDocuments).toHaveBeenCalledTimes(2);
	});
});
