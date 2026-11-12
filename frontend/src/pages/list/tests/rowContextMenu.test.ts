import { afterEach, describe, expect, it, vi } from "vitest";
import { ref } from "vue";
import type { ListRow } from "@/listPage/types";
import type { BulkLayout } from "../bulkLayout";
import { contextMenuOptions, type ContextMenuInput } from "../rowContextMenu";
import { useRowContextMenu } from "../useRowContextMenu";

const row = { name: "A" } as ListRow;
const layout: BulkLayout = {
	transitions: [],
	buttons: [{ label: "Assign", onClick: vi.fn() } as never],
	menu: [
		{ group: "ToDo", options: [{ label: "Restore", onClick: vi.fn() }] },
		{ group: "Delete", theme: "red", options: [{ label: "Delete", theme: "red", onClick: vi.fn() }] },
	],
};

function input(extra: Partial<ContextMenuInput> = {}): ContextMenuInput {
	return {
		row,
		selection: [],
		rowOptions: [{ label: "Archive", onClick: vi.fn() }],
		layout,
		open: vi.fn(),
		openInNewTab: vi.fn(),
		copyLink: vi.fn(),
		...extra,
	};
}

const shape = (options: ReturnType<typeof contextMenuOptions>) =>
	options.map((group) => [
		"group" in group && !group.hideLabel ? group.group : "",
		"options" in group ? group.options.map((one) => ("label" in one ? one.label : "")) : [],
	]);

describe("contextMenuOptions", () => {
	it("gives one record Open, its row actions, then the bulk actions in the bar's order", () => {
		expect(shape(contextMenuOptions(input()))).toEqual([
			["", ["Open", "Open in new tab", "Copy link"]],
			["", ["Archive"]],
			["", ["Assign"]],
			["", ["Restore"]],
			["", ["Delete"]],
		]);
	});

	it("keeps the danger group last and red", () => {
		const groups = contextMenuOptions(input());
		expect(groups.at(-1)).toMatchObject({ theme: "red" });
	});

	it("heads a selected row's menu with the count and leaves out the one-record groups", () => {
		const options = contextMenuOptions(input({ selection: ["A", "B", "C"] }));
		expect(shape(options)).toEqual([
			["3 selected", ["Assign"]],
			["", ["Restore"]],
			["", ["Delete"]],
		]);
	});

	it("keeps the count header neutral when the only bulk group is the red one", () => {
		const danger = { transitions: [], buttons: [], menu: layout.menu.slice(1) };
		const [header] = contextMenuOptions(input({ selection: ["A", "B"], layout: danger }));
		expect(header).toMatchObject({ group: "2 selected", theme: undefined });
	});

	it("shows the one-record menu when the row is the only selection", () => {
		const options = contextMenuOptions(input({ selection: ["A"] }));
		expect(shape(options)[0]).toEqual(["", ["Open", "Open in new tab", "Copy link"]]);
	});

	it("shows the one-record menu without bulk groups when the bar has none", () => {
		const empty = { transitions: [], buttons: [], menu: [] };
		expect(shape(contextMenuOptions(input({ layout: empty, selection: ["A", "B"] })))).toEqual([
			["", ["Open", "Open in new tab", "Copy link"]],
			["", ["Archive"]],
		]);
	});
});

describe("useRowContextMenu", () => {
	afterEach(() => {
		document.body.innerHTML = "";
		window.getSelection()?.removeAllRanges();
	});

	function menu(selected: string[] = []) {
		const selection = ref(selected);
		return { selection, ...useRowContextMenu(selection) };
	}

	function contextmenu(init: MouseEventInit = {}, on: Element = document.body) {
		const event = new MouseEvent("contextmenu", { button: 2, cancelable: true, bubbles: true, clientX: 7, clientY: 9, ...init });
		on.dispatchEvent(event);
		return event;
	}

	it("opens at the pointer and closes", () => {
		const { at, loaded, open, close } = menu();
		const event = contextmenu();
		open("A", event);
		expect(event.defaultPrevented).toBe(true);
		expect(at.value).toEqual({ row: "A", x: 7, y: 9 });
		expect(loaded.value).toBe(true);
		close();
		expect(at.value).toBeNull();
	});

	it("makes an unselected row the only selection, with others selected or with none", () => {
		const others = menu(["B", "C"]);
		others.open("A", contextmenu());
		expect(others.selection.value).toEqual(["A"]);
		const none = menu();
		none.open("A", contextmenu());
		expect(none.selection.value).toEqual(["A"]);
	});

	it("leaves the selection alone on a selected row", () => {
		const { selection, open } = menu(["A", "B"]);
		open("B", contextmenu());
		expect(selection.value).toEqual(["A", "B"]);
	});

	it("leaves the browser's menu on a Shift click, an input and selected text", () => {
		document.body.innerHTML = `<div id="row"><input id="field"><span id="text">hello</span></div>`;
		const { at, open } = menu();

		const shifted = contextmenu({ shiftKey: true });
		open("A", shifted);
		expect(shifted.defaultPrevented).toBe(false);

		const field = contextmenu({}, document.getElementById("field")!);
		open("A", field);
		expect(field.defaultPrevented).toBe(false);

		const text = document.getElementById("text")!;
		const range = document.createRange();
		range.selectNode(text);
		window.getSelection()!.addRange(range);
		const selected = contextmenu({}, text);
		open("A", selected);
		expect(selected.defaultPrevented).toBe(false);
		expect(at.value).toBeNull();
	});

	it("opens on the context-menu key and Shift+F10, which arrive with button 0", () => {
		const { at, open } = menu();
		const event = contextmenu({ button: 0, shiftKey: true });
		open("A", event);
		expect(event.defaultPrevented).toBe(true);
		expect(at.value?.row).toBe("A");
	});
});
