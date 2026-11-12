import { describe, expect, it, vi } from "vitest";
import { editableFields, isEditable, updateFrom, updateRows } from "../bulkEdit";

vi.mock("@framework/ui/api", async (original) => ({
	...(await original<object>()),
	bulkUpdateDocuments: vi.fn(),
}));
import { bulkUpdateDocuments } from "@framework/ui/api";
import { bulkPanel, bulkRunMeta } from "@/shell/bulkOutcome";

const follow = vi.hoisted(() => vi.fn());
vi.mock("@/shell/bulkRuns", () => ({ followBulkRun: follow }));
vi.mock("frappe-ui", () => ({ toast: { success: vi.fn(), info: vi.fn() } }));

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

	it("posts the scope, reloads, and opens the result panel whose Retry sends only the failed names", async () => {
		const reload = vi.fn();
		const select = vi.fn();
		vi.mocked(bulkUpdateDocuments)
			.mockResolvedValueOnce({ data: { total: 2, done: ["A"], failed: [{ name: "B", error: "no" }] } } as never)
			.mockResolvedValueOnce({ data: { total: 1, done: ["B"], failed: [] } } as never);
		await updateRows("Doc", { reload }, { filters: {} }, { values: { x: 1 } }, select);
		expect(bulkUpdateDocuments).toHaveBeenCalledWith("Doc", { filters: {} }, { values: { x: 1 } });
		expect(reload).toHaveBeenCalled();
		expect(bulkPanel.value).toMatchObject({ label: "Edit", failed: [{ name: "B", error: "no" }], select });
		await bulkPanel.value!.retry!(["B"]);
		expect(bulkUpdateDocuments).toHaveBeenLastCalledWith("Doc", { names: ["B"] }, { values: { x: 1 } });
		bulkPanel.value = null;
	});

	it("hands a background run to the tray with its Retry", async () => {
		const reload = vi.fn();
		vi.mocked(bulkUpdateDocuments).mockResolvedValueOnce({ data: { task_id: "T", job_id: "J" } } as never);
		await updateRows("Doc", { reload }, { filters: {} }, { values: { x: 1 } });
		expect(bulkRunMeta.get("T")).toMatchObject({ label: "Edit", doctype: "Doc" });
		expect(bulkRunMeta.get("T")?.retry).toBeTypeOf("function");
		expect(follow).toHaveBeenCalledWith("T", expect.any(Function));
	});
});
