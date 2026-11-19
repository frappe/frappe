import { afterEach, describe, expect, it, vi } from "vitest";
import { ref } from "vue";

const listDocuments = vi.hoisted(() => vi.fn());
const toast = vi.hoisted(() => ({ success: vi.fn(), error: vi.fn() }));
const updateRows = vi.hoisted(() => vi.fn());
vi.mock("@framework/ui/api", () => ({ listDocuments }));
vi.mock("frappe-ui", () => ({ toast }));
vi.mock("@/list/bulkEdit", () => ({ updateRows }));

import type { BulkScope } from "@/list/useBulkScope";
import { useBulkOutput } from "../bulkOutput";
import type { BulkBarOptions } from "../useBulkBar";

function output(picked: string[], loaded: { name: string; title: string }[]) {
	const selection = ref(picked);
	const scope = { selected: vi.fn(() => ({ names: [...selection.value] })), clear: vi.fn() } as unknown as BulkScope;
	const options = {
		doctype: "Note",
		selection,
		scope,
		rows: ref(loaded),
		reload: vi.fn(),
		copy: {
			columns: () => [{ fieldname: "title", label: "Title" }],
			text: (row: Record<string, unknown>, field: string) => String(row[field] ?? ""),
			fields: () => ["name", "title"],
		},
	} as unknown as BulkBarOptions;
	return { out: useBulkOutput(options), selection, scope };
}

const written: unknown[] = [];
class FakeClipboardItem {
	constructor(readonly items: Record<string, Promise<Blob>>) {}
}

function stubClipboard() {
	vi.stubGlobal("ClipboardItem", FakeClipboardItem);
	vi.stubGlobal("navigator", {
		clipboard: {
			writeText: vi.fn(async (text: string) => void written.push(text)),
			write: vi.fn(async ([item]: FakeClipboardItem[]) => void written.push(await (await item.items["text/plain"]).text())),
		},
	});
}

const settle = () => new Promise((resolve) => setTimeout(resolve));

afterEach(() => {
	vi.unstubAllGlobals();
	vi.clearAllMocks();
	written.length = 0;
});

describe("useBulkOutput", () => {
	it("mounts Export on its first ask, with the selection as it was then", () => {
		const { out, selection } = output(["N-1", "N-2"], []);
		expect(out.export.mounted.value).toBe(false);
		out.askExport();
		selection.value = ["N-3"];
		expect([out.export.mounted.value, out.export.open.value]).toEqual([true, true]);
		expect(out.export.selection.value).toEqual({ names: ["N-1", "N-2"] });
	});

	it("mounts Edit on its first ask and reselects the rows the edit failed on", async () => {
		const { out, selection, scope } = output(["N-1", "N-2"], []);
		out.askEdit();
		expect([out.edit.mounted.value, out.edit.open.value]).toEqual([true, true]);
		updateRows.mockImplementation(async (_doctype, _rows, _selection, _update, onFailed) => onFailed(["N-2"]));
		await out.runEdit({ field: "title", value: "x" } as never);
		expect(updateRows.mock.calls[0][2]).toEqual({ names: ["N-1", "N-2"] });
		expect(selection.value).toEqual(["N-2"]);
		expect(scope.clear).toHaveBeenCalled();
	});

	it("copies loaded rows as text in the click", async () => {
		stubClipboard();
		const { out } = output(["N-1"], [{ name: "N-1", title: "One" }]);
		out.copy();
		await settle();
		expect(written).toEqual(["Title\nOne"]);
		expect(listDocuments).not.toHaveBeenCalled();
		expect(toast.success).toHaveBeenCalled();
	});

	it("reads a hidden selected row and copies it in the selection's order", async () => {
		stubClipboard();
		listDocuments.mockResolvedValue({ data: [{ name: "N-9", title: "Nine" }] });
		const { out } = output(["N-9", "N-1"], [{ name: "N-1", title: "One" }]);
		out.copy();
		await settle();
		expect(listDocuments).toHaveBeenCalledWith("Note", expect.objectContaining({ fields: ["name", "title"] }));
		expect(written).toEqual(["Title\nNine\nOne"]);
		expect(toast.success).toHaveBeenCalled();
	});

	it("shows the read's error, not the browser's, when a hidden row cannot be read", async () => {
		stubClipboard();
		listDocuments.mockRejectedValue(new Error("Not permitted"));
		const { out } = output(["N-9"], []);
		out.copy();
		await settle();
		expect(toast.error).toHaveBeenCalledWith(expect.stringContaining("Not permitted"));
	});
});
