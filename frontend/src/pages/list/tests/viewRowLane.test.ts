// The view row's suffix lane: one mark at a time (modified dot, else the default's house), ⋯ only with acts.
import { afterEach, describe, expect, it } from "vitest";
import { createApp, h } from "vue";
import ViewRowLane from "../viewSwitcher/ViewRowLane.vue";

const mounted: ReturnType<typeof createApp>[] = [];
afterEach(() => {
	mounted.splice(0).forEach((app) => app.unmount());
	document.body.innerHTML = "";
});

const ACTS = [{ group: "View", options: [{ label: "Rename" }] }];

function lane(props: Record<string, unknown>): HTMLElement {
	const host = document.body.appendChild(document.createElement("div"));
	const app = createApp({ render: () => h(ViewRowLane, { options: ACTS, ...props }) });
	app.config.globalProperties.__ = (text: string) => text;
	app.mount(host);
	mounted.push(app);
	return host.querySelector("[data-view-lane]") as HTMLElement;
}

const mark = (el: HTMLElement) => [...el.querySelectorAll("[data-view-mark]")].map((one) => one.getAttribute("data-view-mark"));

describe("the view row's lane", () => {
	it("shows the house on the default view", () => {
		const el = lane({ isDefault: true });
		expect(mark(el)).toEqual(["default"]);
		expect(el.querySelector("[data-view-mark]")!.getAttribute("aria-label")).toBe("Default view");
	});

	it("shows a labelled dot instead of the house on a modified view, never both", () => {
		const el = lane({ isDefault: true, modified: true });
		expect(mark(el)).toEqual(["modified"]);
		expect(el.querySelector("[data-view-mark]")!.getAttribute("aria-label")).toBe("Unsaved changes");
	});

	it("shows no mark on a plain view", () => {
		expect(mark(lane({}))).toEqual([]);
	});

	it("draws the ⋯ as a named act control in the same cell as the mark", () => {
		const el = lane({ isDefault: true });
		const button = el.querySelector("button[data-view-menu]")!;
		expect(button.hasAttribute("data-view")).toBe(true);
		expect(button.getAttribute("aria-label")).toBe("View options");
		expect(el.className).toContain("w-7");
		expect(el.className).toContain("grid");
		for (const one of [button, el.querySelector("[data-view-mark]")!]) {
			expect(one.className).toContain("col-start-1");
			expect(one.className).toContain("row-start-1");
		}
	});

	it("keeps the lane's width and the mark when the view has no acts: no ⋯", () => {
		const el = lane({ isDefault: true, options: [] });
		expect(el.querySelector("button")).toBeNull();
		expect(mark(el)).toEqual(["default"]);
		expect(el.querySelector("[data-view-mark]")!.className).not.toContain("opacity-0");
		expect(el.className).toContain("w-7");
	});
});
