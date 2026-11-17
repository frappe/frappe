// The save bar: only a saved view with changes has one; a person who cannot save sees no Save;
// the bulk bar has the spot while rows are selected. The modified mark is one source for all shells.
import { afterEach, describe, expect, it, vi } from "vitest";
import { createApp, defineComponent, effectScope, h, nextTick, ref, type App } from "vue";
import type { View } from "@/list/view";
import { isViewModified, markModifiedView } from "@/list/modifiedView";
import ViewSaveBar from "../ViewSaveBar.vue";
import type { SwitcherHost } from "../viewSwitcher/switcherHost";

type Layer = "own" | "site" | "app" | null;

function setup(layer: Layer, over: { modified?: boolean; saveable?: boolean; drawn?: (act: string) => boolean } = {}) {
	const modified = ref(over.modified ?? true);
	const view = { doctype: "ToDo", key: "mine", layer, modified, saveable: ref(over.saveable ?? true) } as unknown as View;
	const run = vi.fn();
	const host = {
		view: () => ({ key: "mine", label: "Mine", type: "List", layer, modified: modified.value, plainModified: false }),
		drawn: over.drawn ?? (() => true),
		run,
		call: vi.fn(async () => undefined),
	} as unknown as SwitcherHost;
	return { view, host, run, modified };
}

describe("the save bar", () => {
	let app: App | undefined;
	afterEach(() => {
		app?.unmount();
		document.body.innerHTML = "";
	});

	function mount(setupped: ReturnType<typeof setup>, yielding = ref(false)) {
		const root = document.createElement("div");
		document.body.append(root);
		app = createApp(
			defineComponent({
				render: () => h(ViewSaveBar, { view: setupped.view, host: setupped.host, yielding: yielding.value }),
			})
		);
		app.mount(root);
		return { root, yielding };
	}
	const bar = (root: HTMLElement) => root.querySelector("[data-view-save-bar]");
	const buttons = (root: HTMLElement) =>
		[...root.querySelectorAll<HTMLButtonElement>("button")].map((one) => one.textContent?.trim());
	const act = (root: HTMLElement, name: string) => root.querySelector<HTMLButtonElement>(`[data-act="${name}"]`)!;

	it("shows for a saved view with changes: the label, then Discard, Save as new and Save", async () => {
		const { root } = mount(setup("own"));
		await nextTick();
		expect(bar(root)?.textContent).toContain("Unsaved changes to");
		expect(bar(root)?.textContent).toContain("Mine");
		expect(buttons(root)).toEqual(["Discard", "Save as new", "Save"]);
	});

	it("shows nothing for a saved view without changes, and nothing for a plain view", async () => {
		const clean = mount(setup("own", { modified: false }));
		await nextTick();
		expect(bar(clean.root)).toBeNull();
		app?.unmount();
		const plain = mount(setup(null));
		await nextTick();
		expect(plain.root.innerHTML).not.toContain("data-view-save-bar");
		expect(bar(plain.root)).toBeNull();
	});

	it("leaves Save out for a person who cannot save, and makes Save as new the subtle button", async () => {
		const { root } = mount(setup("site", { saveable: false }));
		await nextTick();
		expect(buttons(root)).toEqual(["Discard", "Save as new"]);
		expect(act(root, "list.save_view_as").className).toContain("bg-surface-gray-2");
	});

	it("leaves Save as new ghost beside a subtle Save", async () => {
		const { root } = mount(setup("own"));
		await nextTick();
		expect(act(root, "list.save_view_as").className).not.toContain("bg-surface-gray-2");
		expect(act(root, "list.save_view").className).toContain("bg-surface-gray-2");
	});

	it("gives way to the bulk bar while rows are selected, and comes back", async () => {
		const { root, yielding } = mount(setup("own"));
		await nextTick();
		expect(bar(root)).not.toBeNull();
		yielding.value = true;
		await nextTick();
		await new Promise((done) => setTimeout(done, 50));
		expect(bar(root)).toBeNull();
		yielding.value = false;
		await nextTick();
		expect(bar(root)).not.toBeNull();
	});

	it("runs Discard and Save through the view's acts", async () => {
		const setupped = setup("own");
		const { root } = mount(setupped);
		await nextTick();
		act(root, "list.discard_changes").click();
		expect(setupped.run).toHaveBeenCalledWith("discard_changes");
		act(root, "list.save_view").click();
		expect(setupped.host.call).toHaveBeenCalledWith("save_view");
	});

	it("draws only the acts the page draws", async () => {
		const { root } = mount(setup("own", { drawn: (name) => name === "discard_changes" }));
		await nextTick();
		expect(buttons(root)).toEqual(["Discard"]);
	});
});

describe("the modified mark", () => {
	const scoped = (view: View) => {
		const scope = effectScope();
		scope.run(() => markModifiedView(view));
		return scope;
	};
	const fake = (key: string, layer: Layer, modified: boolean) =>
		({ doctype: "ToDo", key, layer, modified: ref(modified) }) as unknown as View;

	it("marks a saved view with changes, for the crumb and the sidebar to read", () => {
		const scope = scoped(fake("mine", "own", true));
		expect(isViewModified("ToDo", "mine")).toBe(true);
		expect(isViewModified("ToDo", "other")).toBe(false);
		expect(isViewModified("Lead", "mine")).toBe(false);
		scope.stop();
		expect(isViewModified("ToDo", "mine")).toBe(false);
	});

	it("follows the view's changes, and never marks a plain view", async () => {
		const view = fake("mine", "own", false);
		const scope = scoped(view);
		expect(isViewModified("ToDo", "mine")).toBe(false);
		(view.modified as ReturnType<typeof ref>).value = true;
		await nextTick();
		expect(isViewModified("ToDo", "mine")).toBe(true);
		scope.stop();
		const plain = scoped(fake("list", null, true));
		expect(isViewModified("ToDo", "list")).toBe(false);
		plain.stop();
	});
});
