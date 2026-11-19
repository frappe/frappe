// The crumb's modified dot: after the view's label, with an accessible name, only for a saved view with changes.
import { afterEach, describe, expect, it, vi } from "vitest";
import { createApp, defineComponent, h, nextTick, type App } from "vue";
import ViewSwitcher from "../viewSwitcher/ViewSwitcher.vue";
import type { SwitcherHost } from "../viewSwitcher/switcherHost";

vi.mock("@/list/listedViews", () => ({
	useListedViews: () => ({ views: { value: [] }, reload: vi.fn() }),
}));

let app: App | undefined;
afterEach(() => {
	app?.unmount();
	document.body.innerHTML = "";
});

function crumb(modified: boolean) {
	const host = {
		doctype: "ToDo",
		app: "frappe",
		view: () => ({ key: "mine", label: "Mine", type: "List", layer: "own", modified, plainModified: false }),
		admin: false,
		types: [],
		unbuilt: [],
		drawn: () => true,
		run: vi.fn(),
		call: vi.fn(),
	} as unknown as SwitcherHost;
	const root = document.createElement("div");
	document.body.append(root);
	app = createApp(defineComponent({ render: () => h(ViewSwitcher, { host }) }));
	app.config.globalProperties.__ = (text: string) => text;
	app.mount(root);
	return root;
}

describe("the crumb's modified dot", () => {
	it("follows the label, with a name that is not colour alone", async () => {
		const root = crumb(true);
		await nextTick();
		const dot = root.querySelector<HTMLElement>("[data-view-modified]")!;
		expect(dot.getAttribute("aria-label")).toBe("Unsaved changes");
		expect(dot.getAttribute("role")).toBe("img");
		expect(dot.previousElementSibling?.textContent).toBe("Mine");
	});

	it("is not there without changes", async () => {
		const root = crumb(false);
		await nextTick();
		expect(root.querySelector("[data-view-modified]")).toBeNull();
	});
});
