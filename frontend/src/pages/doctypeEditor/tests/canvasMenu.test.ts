// The section menu's move labels are translated when the menu opens, not when the module loads.
import { expect, it, vi, beforeAll } from "vitest";
import { loadText, TEXT_SURFACES } from "@/acts/actText";

const lang = vi.hoisted(() => ({ prefix: "" }));
vi.mock("@/i18n", () => ({ __: (text: string) => lang.prefix + text }));

import { closeContextMenu, openContextMenu } from "../canvasContextMenu";
import { canvasMenu } from "../canvasMenu";
import { mountEditor, taskNote } from "./editorFixture";

// A value waits for its surface's text to load once; load it first so a click acts at once.
beforeAll(() => Promise.all(TEXT_SURFACES.map(loadText)));

it("reads each move label when the menu is built", () => {
	const { canvas, stop } = mountEditor(taskNote());
	lang.prefix = "T:";
	const labels = canvasMenu(canvas, { kind: "section", section: "main" }).map((option) => option.label);
	stop();
	expect(labels.slice(0, 4)).toEqual(["T:Move up", "T:Move down", "T:Move to the tab before", "T:Move to the tab after"]);
});

const twoColumns = () => {
	const note = taskNote();
	const [section] = note.layouts.Details![0].layout[0].sections;
	section.columns = [
		{ name: "column_1", fields: ["subject", "status"] },
		{ name: "column_2", fields: [] },
	];
	return note;
};
const labelsOf = (options: { label: string; disabled?: boolean }[]) =>
	options.map((option) => option.label + (option.disabled ? " (off)" : ""));

it("offers a column the panel's moves, and Remove column only beside another column", () => {
	lang.prefix = "";
	const one = mountEditor(taskNote());
	const two = mountEditor(twoColumns());
	const first = { kind: "column", section: "main", column: "column_1" } as const;
	const lone = labelsOf(canvasMenu(one.canvas, first));
	const beside = labelsOf(canvasMenu(two.canvas, first));
	one.stop();
	two.stop();
	expect(lone).toEqual(["Move left (off)", "Move right (off)"]);
	expect(beside).toEqual(["Move left (off)", "Move right", "Remove column"]);
});

it("offers a field its moves, then its remove, with the other tabs only when there are any", () => {
	lang.prefix = "";
	const { canvas, stop } = mountEditor(taskNote());
	const labels = labelsOf(canvasMenu(canvas, { kind: "field", fieldname: "subject" }));
	stop();
	expect(labels).toEqual([
		"Move up (off)",
		"Move down",
		"Move to the column before (off)",
		"Move to the column after (off)",
		"Remove field",
	]);
});

it("offers nothing on a read-only canvas", () => {
	const { canvas, stop } = mountEditor(taskNote({ modes: [] }));
	const menus = [
		canvasMenu(canvas, { kind: "field", fieldname: "subject" }),
		canvasMenu(canvas, { kind: "section", section: "main" }),
		canvasMenu(canvas, { kind: "column", section: "main", column: "column_1" }),
	];
	stop();
	expect(menus).toEqual([[], [], []]);
});

function rightClick(target: Element, init: MouseEventInit = {}) {
	const event = new MouseEvent("contextmenu", { bubbles: true, cancelable: true, clientX: 30, clientY: 40, ...init });
	Object.defineProperty(event, "target", { value: target });
	return event;
}

it("a right-click selects its target and opens the menu at the pointer, keeping the browser's menu on an input", async () => {
	const { canvas, stop } = mountEditor(taskNote());
	const item = { kind: "field", fieldname: "status" } as const;
	const onInput = rightClick(document.createElement("input"));
	openContextMenu(canvas, onInput, item);
	const event = rightClick(document.createElement("div"));
	openContextMenu(canvas, event, item);
	await Promise.resolve();
	const [opened, selection] = [canvas.contextMenu.value, canvas.selection.value];
	stop();
	expect(onInput.defaultPrevented).toBe(false);
	expect(event.defaultPrevented).toBe(true);
	expect(opened).toEqual({ item, x: 30, y: 40, target: null });
	expect(selection).toEqual(item);
});

it("a right-click on a read-only canvas opens nothing and selects nothing", () => {
	const { canvas, stop } = mountEditor(taskNote({ modes: [] }));
	const event = rightClick(document.createElement("div"));
	openContextMenu(canvas, event, { kind: "field", fieldname: "status" });
	const [opened, selection] = [canvas.contextMenu.value, canvas.selection.value];
	stop();
	expect(event.defaultPrevented).toBe(false);
	expect([opened, selection]).toEqual([null, null]);
});

it("lists the other tabs under Move to tab", () => {
	lang.prefix = "";
	const note = taskNote();
	note.layouts.Details![0].layout.push({
		name: "extra",
		label: "Extra",
		sections: [{ name: "extra_section", columns: [{ name: "column_1", fields: [] }] }],
	});
	const { canvas, stop } = mountEditor(note);
	const options = canvasMenu(canvas, { kind: "field", fieldname: "subject" });
	const move = options.find((option) => option.label === "Move to tab");
	stop();
	expect(move?.submenu?.map((option) => option.label)).toEqual(["Extra"]);
});

it("a right-click in the only column opens nothing of its own: every item there is off, so the section answers", () => {
	const { canvas, stop } = mountEditor(taskNote());
	const event = rightClick(document.createElement("div"));
	openContextMenu(canvas, event, { kind: "column", section: "main", column: "column_1" });
	const [opened, selection] = [canvas.contextMenu.value, canvas.selection.value];
	stop();
	expect(event.defaultPrevented).toBe(false);
	expect([opened, selection]).toEqual([null, null]);
});

it("closing the menu gives the focus back to the element it opened on, for that one call", async () => {
	const { canvas, stop } = mountEditor(taskNote());
	const target = document.createElement("div");
	document.body.append(target);
	canvas.contextMenu.value = { item: { kind: "field", fieldname: "status" }, x: 0, y: 0, target };
	closeContextMenu(canvas);
	await new Promise((done) => setTimeout(done, 150));
	const focused = document.activeElement === target;
	const closed = canvas.contextMenu.value;
	target.blur();
	const tabindex = target.getAttribute("tabindex");
	target.remove();
	stop();
	expect([focused, closed, tabindex]).toEqual([true, null, null]);
});

it("closing the menu leaves the focus on an input the pointer went to", async () => {
	const { canvas, stop } = mountEditor(taskNote());
	const target = document.createElement("div");
	const input = document.createElement("input");
	document.body.append(target, input);
	canvas.contextMenu.value = { item: { kind: "field", fieldname: "status" }, x: 0, y: 0, target };
	closeContextMenu(canvas);
	input.focus();
	await new Promise((done) => setTimeout(done, 150));
	const kept = document.activeElement === input;
	target.remove();
	input.remove();
	stop();
	expect(kept).toBe(true);
});
