// The add-field popover, the drop on the bin and its words, and the panel head's muted title.
import { afterEach, describe, expect, it, vi } from "vitest";
import { createApp, h, nextTick, type App } from "vue";

const { removeField } = vi.hoisted(() => ({ removeField: vi.fn() }));
vi.mock("../fieldPanel", async (importOriginal) => ({
	...(await importOriginal<typeof import("../fieldPanel")>()),
	removeField,
}));

import AddFieldRow from "../AddFieldRow.vue";
import PanelHeader from "../PanelHeader.vue";
import { acts } from "@/acts/dispatcher";
import FieldBin from "../FieldBin.vue";
import { dropField, dropOffLayout, dropOnBin, startDrag } from "../canvasDrops";
import { mountEditor, taskNote } from "./editorFixture";

let app: App | undefined;
let stop: (() => void) | undefined;
afterEach(() => {
	app?.unmount();
	stop?.();
	app = stop = undefined;
	document.body.innerHTML = "";
	removeField.mockClear();
});

async function settle() {
	for (let i = 0; i < 4; i++) await nextTick();
	await new Promise((resolve) => setTimeout(resolve, 0));
}

function mount(render: (editor: ReturnType<typeof mountEditor>) => ReturnType<typeof h>) {
	const editor = mountEditor(taskNote());
	stop = editor.stop;
	app = createApp({ render: () => render(editor) }).provide("addresses", { doctypes: () => [] });
	app.mount(document.body.appendChild(document.createElement("div")));
	return editor;
}

describe("AddFieldRow", () => {
	async function openRow() {
		const editor = mount((e) => h(AddFieldRow, { canvas: e.canvas, section: "main" }));
		editor.canvas.adding.value = "main";
		await settle();
		return editor;
	}

	function type(text: string) {
		const input = document.querySelector<HTMLInputElement>("[data-canvas-add-row] input")!;
		input.value = text;
		input.dispatchEvent(new Event("input", { bubbles: true }));
		return settle();
	}

	it("says which word its type guess came from", async () => {
		await openRow();
		expect(document.querySelector("[data-canvas-add-row]")!.textContent).toContain("Guessed from the label");
		await type("Due date");
		const row = document.querySelector("[data-canvas-add-row]")!;
		expect(row.textContent).toContain("Guessed from 'date'");
		expect(row.querySelector("[data-canvas-guessed-type]")!.textContent).toContain("Date");
	});

	it("adds the field and stays open, empty, for the next one", async () => {
		const editor = await openRow();
		const before = editor.canvas.working.value.fields.length;
		await type("Due date");
		document.querySelector<HTMLFormElement>("[data-canvas-add-row]")!.requestSubmit();
		await vi.waitFor(() => expect(editor.canvas.working.value.fields.length).toBe(before + 1));
		await settle();
		expect(editor.canvas.working.value.fields.at(-1)).toMatchObject({ label: "Due date", fieldtype: "Date" });
		expect(editor.canvas.adding.value).toBe("main");
		expect(document.querySelector<HTMLInputElement>("[data-canvas-add-row] input")!.value).toBe("");
	});
});

describe("dropping on the bin", () => {
	function drag(overBin: boolean, fieldname: string | undefined = "subject") {
		const editor = mount(() => h("div"));
		editor.canvas.drag.value = { active: true, overBin, fieldname };
		return editor.canvas;
	}

	it("removes the field released over the bin, and ends the drag", () => {
		const canvas = drag(true);
		dropOnBin(canvas);
		expect(removeField).toHaveBeenCalledWith(canvas, canvas.field("subject"));
		expect(canvas.drag.value).toEqual({ active: false, overBin: false });
	});

	it("does nothing for a field released elsewhere", () => {
		const canvas = drag(false);
		dropOnBin(canvas);
		expect(removeField).not.toHaveBeenCalled();
		expect(canvas.drag.value.active).toBe(false);
	});

	it("does nothing for a name that is no field", () => {
		dropOnBin(drag(true, "nope"));
		expect(removeField).not.toHaveBeenCalled();
	});

	it("keeps a hidden field hidden where the bin hides", () => {
		const canvas = drag(true);
		const field = { fieldname: "subject", hidden: 1 };
		const fake = { drag: canvas.drag, field: () => field, customize: { hidesOnRemove: () => true } };
		dropOnBin(fake as any);
		expect(removeField).not.toHaveBeenCalled();
		fake.field = () => ({ fieldname: "subject", hidden: 0 }) as any;
		canvas.drag.value = { active: true, overBin: true, fieldname: "subject" };
		dropOnBin(fake as any);
		expect(removeField).toHaveBeenCalledTimes(1);
	});

	it("names the dragged field from its item, whatever the column's order became", () => {
		const canvas = drag(false, undefined);
		const item = document.createElement("div");
		item.dataset.canvasField = "status";
		startDrag(canvas, item);
		expect(canvas.drag.value).toEqual({ active: true, overBin: false, fieldname: "status" });
	});

	it("moves nothing when the drop is under the bin", async () => {
		const canvas = drag(true);
		const move = vi.spyOn(acts, "perform").mockResolvedValue(undefined as any);
		dropField(canvas, { moved: { element: "subject", newIndex: 0 } }, { section: "main", column: "c1" });
		expect(move).not.toHaveBeenCalled();
		canvas.drag.value = { active: true, overBin: false };
		dropField(canvas, { moved: { element: "subject", newIndex: 0 } }, { section: "main", column: "c1" });
		expect(move).toHaveBeenCalledWith("canvas.move_field", expect.objectContaining({ fieldname: "subject" }));
		move.mockRestore();
	});

	it("takes a field off the layout from the tray, except under the bin", () => {
		const canvas = drag(true);
		const move = vi.spyOn(acts, "perform").mockResolvedValue(undefined as any);
		dropOffLayout(canvas, { added: { element: "subject", newIndex: 0 } });
		expect(move).not.toHaveBeenCalled();
		canvas.drag.value = { active: true, overBin: false };
		dropOffLayout(canvas, { added: { element: "subject", newIndex: 0 } });
		expect(move).toHaveBeenCalledWith("canvas.unplace_field", { fieldname: "subject" });
		move.mockRestore();
	});
});

describe("FieldBin", () => {
	function bin() {
		const editor = mount((e) => h(FieldBin, { canvas: e.canvas }));
		const pill = document.querySelector<HTMLElement>("[data-canvas-bin]")!;
		pill.getBoundingClientRect = () => ({ left: 100, right: 200, top: 100, bottom: 136 }) as DOMRect;
		return { canvas: editor.canvas, pill };
	}

	function move(x: number, y: number) {
		window.dispatchEvent(new PointerEvent("pointermove", { clientX: x, clientY: y }));
		return settle();
	}

	it("follows the pointer only while a field is dragged", async () => {
		const { canvas } = bin();
		await move(150, 118);
		expect(canvas.drag.value.overBin).toBe(false);
		canvas.drag.value = { active: true, overBin: false, fieldname: "subject" };
		await settle();
		await move(150, 118);
		expect(canvas.drag.value.overBin).toBe(true);
		await move(150, 300);
		expect(canvas.drag.value.overBin).toBe(false);
	});

	it("words the drop as the panel trash does", async () => {
		const { canvas, pill } = bin();
		canvas.drag.value = { active: true, overBin: false, fieldname: "subject" };
		await settle();
		expect(pill.textContent).toContain("Drop here to remove");
		canvas.drag.value = { active: true, overBin: true, fieldname: "subject" };
		await settle();
		expect(pill.textContent).toContain("Release to remove");
	});
});

describe("PanelHeader", () => {
	function title(muted?: boolean) {
		const root = document.body.appendChild(document.createElement("div"));
		app = createApp({ render: () => h(PanelHeader, { icon: "lucide-box", title: "Details", subtitle: "Tab", muted }) });
		app.mount(root);
		return root.querySelector("[data-panel-title]")!;
	}

	it("greys the title when muted", () => {
		expect(title(true).className).toContain("text-ink-gray-4");
	});

	it("keeps the title dark otherwise", () => {
		const el = title();
		expect(el.className).toContain("text-ink-gray-9");
		expect(el.className).not.toContain("text-ink-gray-4");
	});
});
