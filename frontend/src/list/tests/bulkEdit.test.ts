import { describe, expect, it, vi } from "vitest";
import { editableFields, isEditable, updateFrom, updateRows } from "../bulkEdit";

vi.mock("@framework/ui/api", async (original) => ({
	...(await original<object>()),
	bulkUpdateDocuments: vi.fn(),
}));
import { bulkUpdateDocuments } from "@framework/ui/api";

const field = (fieldname: string, extra: Record<string, unknown> = {}) =>
	({ fieldname, label: fieldname.toUpperCase(), fieldtype: "Data", ...extra }) as never;

describe("bulk edit fields", () => {
	it("allows value fields that are not read-only, hidden or virtual", () => {
		expect(isEditable(field("a"))).toBe(true);
		expect(isEditable(field("a", { read_only: 1 }))).toBe(false);
		expect(isEditable(field("a", { hidden: 1 }))).toBe(false);
		expect(isEditable(field("a", { is_virtual: 1 }))).toBe(false);
		expect(isEditable(field("a", { fieldtype: "Section Break" }))).toBe(false);
		expect(isEditable(field("a", { fieldtype: "Table" }))).toBe(false);
	});

	it("lists a table's editable fields under the table, sorted by label", () => {
		const own = [field("title"), field("items", { fieldtype: "Table", label: "Items", options: "Row" })];
		const keys = editableFields("Doc", own, { Row: [field("qty"), field("ro", { read_only: 1 })] }).map((one) => one.key);
		expect(keys).toEqual(["items.qty", "title"]);
	});
});

describe("bulk edit request", () => {
	it("sets several fields in one values and one child_values, an empty value clearing", () => {
		const fields = editableFields("Doc", [field("title"), field("items", { fieldtype: "Table", options: "Row" })], {
			Row: [field("qty")],
		});
		const [title, qty] = ["title", "items.qty"].map((key) => fields.find((one) => one.key === key)!);
		const picked = [
			{ field: title, value: "" },
			{ field: qty, value: 3 },
		];
		expect(updateFrom(picked.slice(0, 1))).toEqual({ values: { title: null } });
		expect(updateFrom(picked)).toEqual({ values: { title: null }, child_values: { items: { qty: 3 } } });
	});

	it("posts the scope, reloads and reports what failed", async () => {
		const reload = vi.fn();
		vi.mocked(bulkUpdateDocuments).mockResolvedValueOnce({
			data: { total: 2, done: ["A"], failed: [{ name: "B", error: "no" }] },
		} as never);
		const outcome = await updateRows("Doc", { reload }, { names: ["A", "B"] }, { values: { x: 1 } });
		expect(bulkUpdateDocuments).toHaveBeenCalledWith("Doc", { names: ["A", "B"] }, { values: { x: 1 } });
		expect(reload).toHaveBeenCalled();
		expect(outcome).toEqual({ updated: ["A"], failed: [{ name: "B", error: "no" }] });
	});

	it("hands a background run's task to the caller", async () => {
		vi.mocked(bulkUpdateDocuments).mockResolvedValueOnce({ data: { task_id: "T", job_id: "J" } } as never);
		const outcome = await updateRows("Doc", { reload: vi.fn() }, { filters: {} }, { values: { x: 1 } });
		expect(outcome.queued).toEqual({ task_id: "T" });
	});
});
