// The panel shuts the way it opens: the content stays under the shrinking width and the
// strip appears only once the transition has settled.
import { afterEach, describe, expect, it, vi } from "vitest";
import { createApp, defineComponent, h, nextTick } from "vue";

vi.mock("../PanelEdge.vue", () => ({
	default: defineComponent({
		emits: ["toggle"],
		setup: (_, { emit }) => () => h("button", { "data-edge": "", onClick: () => emit("toggle") }),
	}),
}));
vi.mock("../PanelLayout.vue", () => ({
	default: defineComponent({ render: () => h("div", { "data-content": "" }) }),
}));
vi.mock("../QuickActions.vue", () => ({
	default: defineComponent({ render: () => h("div", { "data-strip": "" }) }),
}));

import RecordPanel from "../RecordPanel.vue";

const mounted: ReturnType<typeof createApp>[] = [];

afterEach(() => {
	for (const app of mounted.splice(0)) app.unmount();
	document.body.innerHTML = "";
	localStorage.clear();
	vi.useRealTimers();
});

async function mount() {
	const root = document.createElement("div");
	document.body.appendChild(root);
	const app = createApp(
		defineComponent({
			render: () =>
				h(RecordPanel, {
					user: "tester",
					doctype: "Note",
					docname: "N-1",
					controller: { panelSections: { isVisible: () => true }, page: {} } as any,
					meta: {},
					docinfo: null,
					sections: [],
					disclosure: { isOpen: () => true, toggle() {} } as any,
					run() {},
					reloadDocinfo: async () => {},
					doc: {},
				}),
		})
	);
	app.mount(root);
	mounted.push(app);
	await nextTick();
	return root;
}

const toggle = (root: HTMLElement) => root.querySelector<HTMLButtonElement>("[data-edge]")!.click();
const content = (root: HTMLElement) => root.querySelector("[data-content]");
const strip = (root: HTMLElement) => root.querySelector("[data-strip]");

function endWidthTransition(root: HTMLElement) {
	const event = new Event("transitionend");
	Object.defineProperty(event, "propertyName", { value: "width" });
	root.querySelector("[data-record-panel]")!.dispatchEvent(event);
}

describe("closing", () => {
	it("keeps the content mounted until the width transition ends, then shows the strip", async () => {
		const root = await mount();
		toggle(root);
		await nextTick();
		expect(content(root)).not.toBeNull();
		expect(strip(root)).toBeNull();

		endWidthTransition(root);
		await nextTick();
		expect(content(root)).toBeNull();
		expect(strip(root)).not.toBeNull();
	});

	it("settles on the timer when no transitionend arrives", async () => {
		vi.useFakeTimers();
		const root = await mount();
		toggle(root);
		await nextTick();
		expect(content(root)).not.toBeNull();

		vi.advanceTimersByTime(300);
		await nextTick();
		expect(content(root)).toBeNull();
		expect(strip(root)).not.toBeNull();
	});

	it("ignores a transitionend for another property", async () => {
		const root = await mount();
		toggle(root);
		await nextTick();
		const event = new Event("transitionend");
		Object.defineProperty(event, "propertyName", { value: "opacity" });
		root.querySelector("[data-record-panel]")!.dispatchEvent(event);
		await nextTick();
		expect(content(root)).not.toBeNull();
	});
});

describe("opening", () => {
	it("mounts the content at once", async () => {
		const root = await mount();
		toggle(root);
		await nextTick();
		endWidthTransition(root);
		await nextTick();
		expect(strip(root)).not.toBeNull();

		toggle(root);
		await nextTick();
		expect(content(root)).not.toBeNull();
		expect(strip(root)).toBeNull();
	});
});
