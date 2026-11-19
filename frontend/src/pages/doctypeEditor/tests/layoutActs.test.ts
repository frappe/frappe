// The `layouts` acts the layout menu runs, and a field taken off a layout other than Details.
import { afterEach, describe, expect, it, vi } from "vitest";

const { toast } = vi.hoisted(() => ({ toast: { error: vi.fn(), success: vi.fn() } }));
vi.mock("frappe-ui", () => ({ toast }));

import { acts } from "@/acts/dispatcher";
import { removeAction, takeOff } from "../fieldPanel";
import { mountEditor } from "./editorFixture";
import { leadNote } from "./layoutsFixture";

let mounted: ReturnType<typeof mountEditor>;
afterEach(() => {
	mounted.stop();
	toast.error.mockClear();
});

function mount(state = leadNote()) {
	mounted = mountEditor(state);
	return mounted.canvas;
}

describe("the layouts acts", () => {
	it("open a layout on the Editor tab from any tab", async () => {
		const canvas = mount();
		await acts.run("editor.open_tab", "preview");
		await acts.run("layouts.open", { type: "Side Panel" });
		expect(canvas.openLayout.value).toEqual({ type: "Side Panel" });
		expect(mounted.tab.value).toBe("editor");
	});

	it("add a layout, then open it", async () => {
		const canvas = mount();
		await acts.run("layouts.add", { type: "Details", title: "Partners", condition: "doc.partner", start: "empty" });
		const [edit] = mounted.edits.staged.value;
		expect(edit).toMatchObject({ act: "layouts.add", type: "Details", title: "Partners", condition: "doc.partner" });
		expect(canvas.openLayout.value).toEqual({ type: "Details", id: edit.id });
		expect(canvas.layout.value?.title).toBe("Partners");
	});

	it("refuse a second default layout of a type, and stage nothing", async () => {
		mount();
		await acts.perform("layouts.add", { type: "Details", title: "", condition: "", start: "copy" });
		expect(mounted.edits.staged.value).toEqual([]);
		expect(toast.error).toHaveBeenCalledOnce();
	});

	it("rename, condition and delete the open conditional layout", async () => {
		const canvas = mount();
		const layout = { type: "Details", id: "app:1" } as const;
		await acts.run("layouts.open", layout);
		await acts.run("layouts.rename", { layout, title: "Closed" });
		await acts.run("layouts.set_condition", { layout, condition: "doc.status == 'Closed'" });
		expect(canvas.layout.value).toMatchObject({ title: "Closed", condition: "doc.status == 'Closed'" });
		await acts.run("layouts.delete", { layout });
		expect(canvas.openLayout.value).toEqual({ type: "Details" });
		expect(mounted.edits.staged.value.map((edit) => edit.act)).toEqual([
			"layouts.rename",
			"layouts.set_condition",
			"layouts.delete",
		]);
	});
});

describe("a site row the address names on a standard DocType in Design", () => {
	it("opens the type's default: Design reads the app's layouts", () => {
		const canvas = mount();
		canvas.open({ type: "Details", id: "FL-1" });
		expect(canvas.openLayout.value).toEqual({ type: "Details" });
	});

	it("opens in Customize, which reads the site rows", () => {
		const canvas = mount(leadNote({ mode: "Customize" }));
		canvas.open({ type: "Details", id: "FL-1" });
		expect(canvas.openLayout.value).toEqual({ type: "Details", id: "FL-1" });
	});
});

describe("Take off this layout", () => {
	it("is the remove of a placed field outside Details, and returns it to the tray", async () => {
		const canvas = mount();
		await acts.run("layouts.open", { type: "Quick Entry" });
		const notes = canvas.field("notes")!;
		expect(removeAction(canvas, notes).label).toBe("Take off this layout");
		canvas.select({ kind: "field", fieldname: "notes" });
		await takeOff(canvas, "notes");
		expect(canvas.selection.value).toBeNull();
		expect(canvas.offLayout.value.map(({ field }) => field.fieldname)).toContain("notes");
		expect(canvas.field("notes")).toBeTruthy();
		expect(removeAction(canvas, notes).label).toBe("");
	});

	it("leaves Details' remove as Remove field", () => {
		const canvas = mount();
		expect(removeAction(canvas, canvas.field("subject")!).label).toBe("Remove field");
	});
});

