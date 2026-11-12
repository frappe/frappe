// The list's selection keys, through the shell's key binder and the dispatcher as in the app.
import { afterEach, describe, expect, it, vi } from "vitest";
import { createApp, defineComponent, h, nextTick, ref, type App } from "vue";
import { acts } from "@/acts/dispatcher";
import { ActKeys } from "@/shell/actKeys";
import { bulkKeyEntries } from "../bulkKeys";

const apps: App[] = [];
const unregisters: (() => void)[] = [];

afterEach(() => {
	for (const app of apps.splice(0)) app.unmount();
	for (const unregister of unregisters.splice(0)) unregister();
	document.body.innerHTML = "";
});

function setup({ selected = [] as string[], cursor = null as string | null, menu = true } = {}) {
	const selection = ref(selected);
	const cursorRow = ref(cursor);
	const menuOpen = ref(false);
	const toggle = vi.fn();
	const extendTo = vi.fn();
	unregisters.push(
		acts.register({
			surfaces: {
				list: () =>
					bulkKeyEntries({
						selection,
						cursor: cursorRow,
						shown: (name) => ["A", "B"].includes(name),
						locked: false,
						hasMenu: () => menu,
						menuOpen,
						toggle,
						extendTo,
					}),
			},
			context: () => ({}),
			passes: () => true,
			settled: () => undefined,
			hold: async (work) => work(),
			failed: () => {},
		})
	);
	const app = createApp(defineComponent({ render: () => [h("input", { name: "field" }), h(ActKeys)] }));
	app.mount(document.body.appendChild(document.createElement("div")));
	apps.push(app);
	return { selection, cursorRow, menuOpen, toggle, extendTo };
}

async function press(key: string, extra: KeyboardEventInit = {}, target: Element = document.body) {
	await nextTick();
	target.dispatchEvent(new KeyboardEvent("keydown", { key, bubbles: true, cancelable: true, ...extra }));
	await new Promise((resolve) => setTimeout(resolve, 0));
}

describe("bulk selection keys", () => {
	it("x toggles the row under the cursor, and Shift+X extends to it", async () => {
		const { toggle, extendTo } = setup({ cursor: "B" });
		await press("x");
		expect(toggle).toHaveBeenCalledWith("B");
		await press("X", { shiftKey: true });
		expect(extendTo).toHaveBeenCalledWith("B");
		expect(toggle).toHaveBeenCalledOnce();
	});

	it("does nothing on x without a cursor row, or when the row is no longer shown", async () => {
		const none = setup();
		await press("x");
		expect(none.toggle).not.toHaveBeenCalled();

		none.cursorRow.value = "Z";
		await press("x");
		expect(none.toggle).not.toHaveBeenCalled();
	});

	it("does nothing while typing in an input", async () => {
		const { toggle, menuOpen, selection } = setup({ cursor: "A", selected: ["A"] });
		const input = document.querySelector("input")!;
		await press("x", {}, input);
		await press(".", { code: "Period" }, input);
		await press("Escape", {}, input);
		expect(toggle).not.toHaveBeenCalled();
		expect(menuOpen.value).toBe(false);
		expect(selection.value).toEqual(["A"]);
	});

	it(". opens the bar's menu only with a selection and a menu to open", async () => {
		const empty = setup();
		await press(".", { code: "Period" });
		expect(empty.menuOpen.value).toBe(false);
		empty.selection.value = ["A"];
		await press(".", { code: "Period" });
		expect(empty.menuOpen.value).toBe(true);
	});

	it(". does nothing when the bar has no menu", async () => {
		const { menuOpen } = setup({ selected: ["A"], menu: false });
		await press(".", { code: "Period" });
		expect(menuOpen.value).toBe(false);
	});

	it("Esc clears the selection, and leaves Esc alone without one", async () => {
		const { selection } = setup({ selected: ["A", "B"] });
		await press("Escape");
		expect(selection.value).toEqual([]);

		const event = new KeyboardEvent("keydown", { key: "Escape", bubbles: true, cancelable: true });
		document.body.dispatchEvent(event);
		expect(event.defaultPrevented).toBe(false);
	});

	it("lists . and Esc for the palette, and not the row keys", () => {
		const entries = bulkKeyEntries({
			selection: ref(["A"]),
			cursor: ref("A"),
			shown: () => true,
			locked: false,
			hasMenu: () => true,
			menuOpen: ref(false),
			toggle: vi.fn(),
			extendTo: vi.fn(),
		});
		const listed = entries.filter(({ item }) => item.palette !== false).map(({ item }) => item.key);
		expect(listed).toEqual(["Period", "Escape"]);
	});
});
