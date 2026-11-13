import { afterEach, describe, expect, it, vi } from "vitest";

const { toast } = vi.hoisted(() => ({ toast: { error: vi.fn(), success: vi.fn() } }));
vi.mock("frappe-ui", () => ({ toast }));

import { acts } from "@/acts/dispatcher";
import type { LayoutRef } from "../workingLayouts";
import { mountEditor } from "./editorFixture";
import { leadNote } from "./layoutsFixture";

let mounted: ReturnType<typeof mountEditor>;
afterEach(() => mounted.stop());

const tray = () =>
	mounted.canvas.offLayout.value.map(({ field, ...marks }) => ({ fieldname: field.fieldname, ...marks }));

function open(layout: LayoutRef) {
	mounted = mountEditor(leadNote());
	mounted.canvas.open(layout);
	return mounted.canvas;
}

describe("the open layout", () => {
	it("is the default Details layout until another opens", () => {
		mounted = mountEditor(leadNote());
		expect(mounted.canvas.openLayout.value).toEqual({ type: "Details" });
		expect(mounted.canvas.tabs.value[0].sections[0].columns[0].fields).toEqual(["subject", "status"]);
	});

	it("names every canvas edit the UI stages", async () => {
		const canvas = open({ type: "Details", id: "app:1" });
		await acts.run("canvas.place_field", { fieldname: "notes", section: "main", column: "column_1" });
		await acts.run("fields.add_field", { label: "Ref", fieldtype: "Data", section: "main", column: "column_1" });
		expect(mounted.edits.staged.value.map((edit) => edit.layout)).toEqual([
			{ type: "Details", id: "app:1" },
			{ type: "Details", id: "app:1" },
		]);
		expect(canvas.tabs.value[0].sections[0].columns[0].fields).toEqual(["subject", "notes", "ref"]);
	});

	it("falls back to its type's default once it is deleted", async () => {
		const canvas = open({ type: "Details", id: "app:1" });
		canvas.stage({ act: "layouts.delete", layout: { type: "Details", id: "app:1" } });
		expect(canvas.openLayout.value).toEqual({ type: "Details" });
	});
});

describe("the tray of each layout", () => {
	it("Details lists what its default leaves off, with the asked mark", () => {
		const canvas = open({ type: "Details" });
		canvas.askedOnSave.value = ["notes"];
		expect(tray()).toEqual([
			{ fieldname: "notes", new: false, asked: true },
			{ fieldname: "spare", new: false, asked: false },
		]);
	});

	it("Side Panel lists every field until one is placed, with the new mark", async () => {
		const canvas = open({ type: "Side Panel" });
		await acts.run("fields.add_field", { label: "Ref", fieldtype: "Data" });
		await acts.run("canvas.place_field", { fieldname: "status", section: "section_1", column: "column_1" });
		expect(tray()).toEqual([
			{ fieldname: "subject", new: false, asked: false },
			{ fieldname: "notes", new: false, asked: false },
			{ fieldname: "spare", new: false, asked: false },
			{ fieldname: "ref", new: true, asked: false },
		]);
		expect(canvas.layout.value?.source).toBe("app");
	});

	it("Quick Entry lists what its fallback does not ask for", () => {
		open({ type: "Quick Entry" });
		expect(tray().map((row) => row.fieldname)).toEqual(["subject", "status"]);
	});

	it("New Record reads Details until it has its own", async () => {
		open({ type: "New Record" });
		expect(tray().map((row) => row.fieldname)).toEqual(["notes", "spare"]);
		await acts.run("canvas.place_field", { fieldname: "notes", section: "main", column: "column_1" });
		expect(tray().map((row) => row.fieldname)).toEqual(["spare"]);
		mounted.canvas.open({ type: "Details" });
		expect(tray().map((row) => row.fieldname)).toEqual(["notes", "spare"]);
	});
});
