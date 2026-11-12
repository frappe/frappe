import { afterEach, describe, expect, it, vi } from "vitest";
import { createApp, defineComponent, h, nextTick, ref, type App } from "vue";
import { createListPageLists } from "@/listPage/createListPage";
import type { ListPageAction } from "@/listPage/types";
import BulkBar from "../BulkBar.vue";
import { layoutBulk, type BulkEntry } from "../bulkLayout";
import { useBulkBar } from "../useBulkBar";

const entry = (name: string, extra: Partial<BulkEntry> = {}): BulkEntry => ({
	name,
	label: name,
	onClick: vi.fn(),
	...extra,
});

const labels = (menu: { group: string; options: { label: string }[] }[]) =>
	menu.map((group) => [group.group, group.options.map((option) => option.label)]);

describe("layoutBulk", () => {
	it("puts Delete in the danger group, in red, and as a trash icon", () => {
		const layout = layoutBulk([entry("delete", { group: "danger" })], "ToDo");
		expect(layout.trash?.name).toBe("delete");
		expect(layout.menu).toEqual([
			{
				group: "Submit, cancel and delete",
				theme: "red",
				options: [expect.objectContaining({ label: "delete", theme: "red" })],
			},
		]);
	});

	it("draws a script's item as an app action, first in More under the doctype's name", () => {
		const layout = layoutBulk(
			[entry("delete", { group: "danger" }), entry("restore"), entry("tag", { group: "collaborate" })],
			"ToDo"
		);
		expect(labels(layout.menu)).toEqual([
			["ToDo", ["restore"]],
			["Assign, tag and share", ["tag"]],
			["Submit, cancel and delete", ["delete"]],
		]);
	});

	it("keeps a button out of More and orders the groups app, collaborate, output, danger", () => {
		const layout = layoutBulk(
			[
				entry("delete", { group: "danger" }),
				entry("print", { group: "output" }),
				entry("assign", { group: "collaborate", button: true }),
				entry("share", { group: "collaborate" }),
				entry("mine"),
			],
			"ToDo"
		);
		expect(layout.buttons.map((one) => one.name)).toEqual(["assign"]);
		expect(labels(layout.menu)).toEqual([
			["ToDo", ["mine"]],
			["Assign, tag and share", ["share"]],
			["Print and export", ["print"]],
			["Submit, cancel and delete", ["delete"]],
		]);
	});

	it("keeps up to two workflow transitions as the first buttons, and moves more into a Workflow group", () => {
		const two = layoutBulk([entry("a", { group: "workflow" }), entry("b", { group: "workflow" })], "ToDo");
		expect(two.transitions).toHaveLength(2);
		expect(two.menu).toEqual([]);

		const three = layoutBulk(
			["a", "b", "c"].map((name) => entry(name, { group: "workflow" })),
			"ToDo"
		);
		expect(three.transitions).toEqual([]);
		expect(labels(three.menu)).toEqual([["Workflow", ["a", "b", "c"]]]);

		const flagged = layoutBulk(
			["a", "b", "c"].map((name) => entry(name, { group: "workflow", button: true })),
			"ToDo"
		);
		expect(labels(flagged.menu)).toEqual([["Workflow", ["a", "b", "c"]]]);
	});
});

describe("BulkBar", () => {
	let app: App | null = null;
	afterEach(() => {
		app?.unmount();
		document.body.innerHTML = "";
	});

	function mount(props: Record<string, unknown>) {
		const root = document.createElement("div");
		document.body.append(root);
		const clear = vi.fn();
		app = createApp(defineComponent({ render: () => h(BulkBar, { cap: 500, locked: false, ...props, onClear: clear } as never) }));
		app.mount(root);
		return { root, clear };
	}

	const button = (root: HTMLElement, label: string) =>
		root.querySelector<HTMLButtonElement>(`button[aria-label="${label}"], button[title="${label}"]`) ??
		[...root.querySelectorAll("button")].find((one) => one.textContent?.trim() === label);

	it("shows the count, runs a button and the trash icon, and clears", async () => {
		const edit = entry("edit", { label: "Edit", button: true });
		const trash = entry("delete", { label: "Delete", icon: "lucide-trash-2", group: "danger" });
		const { root, clear } = mount({ count: 3, layout: layoutBulk([edit, trash], "ToDo") });
		expect(root.textContent).toContain("3 selected");

		button(root, "Edit")!.click();
		expect(edit.onClick).toHaveBeenCalledOnce();
		button(root, "Delete")!.click();
		expect(trash.onClick).toHaveBeenCalledOnce();
		button(root, "Clear selection")!.click();
		expect(clear).toHaveBeenCalledOnce();
	});

	it("opens More on a click, with its Tooltip around the button", async () => {
		const { root } = mount({ count: 2, layout: layoutBulk([entry("edit", { label: "Edit" })], "ToDo") });
		button(root, "More")!.click();
		await nextTick();
		expect(document.body.querySelector("[role=menu]")?.textContent).toContain("Edit");
	});

	it("says it is over the cap", () => {
		const { root } = mount({ count: 501, layout: layoutBulk([entry("edit", { button: true })], "ToDo") });
		expect(root.textContent).toContain("Over the 500 cap");
	});

	it("draws no action when the person's bulk actions switch is off", () => {
		const { root } = mount({ count: 2, locked: true, layout: layoutBulk([], "ToDo") });
		expect(root.textContent).toContain("2 selected");
		expect(root.textContent).not.toContain("More");
		expect(root.textContent).not.toContain("Over the");
	});
});

describe("useBulkBar", () => {
	function bar(boot: Record<string, unknown>, drawn: (name: string) => unknown = (name) => ({ name, label: name })) {
		const lists = createListPageLists();
		const selection = ref(["A", "B"]);
		const perform = vi.fn();
		const askDelete = vi.fn();
		const supplied: Array<() => Array<{ item: { name: string } }>> = [];
		let result!: ReturnType<typeof useBulkBar>;
		const root = document.createElement("div");
		const app = createApp(
			defineComponent({
				setup() {
					result = useBulkBar({
						host: { lists, acts: (supply: never) => (supplied.push(supply), { drawn, perform }) } as never,
						doctype: "ToDo",
						selection,
						rows: ref([]),
						rowActions: ref([]),
						reload: () => {},
						askDelete,
						cursor: ref(null),
						table: () => null,
					});
					return () => null;
				},
			})
		);
		app.provide("boot", boot).mount(root);
		return { result, lists, selection, perform, askDelete, supplied, app };
	}

	const open = { bulk_actions: true, bulk_operation_limit: 500 };
	const script = (name: string): ListPageAction => ({ name, label: name, run: () => {} });

	it("draws Delete and a script's item, running each on the frozen selection", async () => {
		const { result, lists, selection, perform, app } = bar(open);
		lists.bulkActions.add(script("restore"));
		await nextTick();
		const { layout } = result;
		expect(labels(layout.value.menu)).toEqual([
			["ToDo", ["restore"]],
			["Submit, cancel and delete", ["delete"]],
		]);

		layout.value.menu[0].options[0].onClick();
		selection.value = ["C"];
		expect(perform).toHaveBeenCalledWith(expect.objectContaining({ name: "restore" }), ["A", "B"]);
		app.unmount();
	});

	it("hides an item the dispatcher does not draw, and all of them without the switch", () => {
		const refused = bar(open, (name) => (name === "delete" ? undefined : { name, label: name }));
		expect(refused.result.layout.value.trash).toBeUndefined();
		refused.app.unmount();

		const locked = bar({ bulk_actions: false, bulk_operation_limit: 500 });
		expect(locked.result.locked).toBe(true);
		expect(locked.supplied[0]().map(({ item }) => item.name)).not.toContain("delete");
		expect(locked.result.layout.value.menu).toEqual([]);
		locked.app.unmount();
	});

	it("disables the actions over the cap", () => {
		const over = bar({ bulk_actions: true, bulk_operation_limit: 1 });
		expect(over.result.layout.value.trash?.disabled).toBe(true);
		over.app.unmount();
	});
});
