// The page frame: its header row teleports to the shell's target, and `scroll` picks who scrolls.
import { afterEach, describe, expect, it } from "vitest";
import { createApp, defineComponent, h, nextTick, type Component } from "vue";
import { PageHeaderTarget } from "frappe-ui";

import PageFrame, { pageGutter } from "../PageFrame.vue";

const mounted: ReturnType<typeof createApp>[] = [];

afterEach(() => {
	for (const app of mounted.splice(0)) app.unmount();
	document.body.innerHTML = "";
});

/** A shell in miniature: the pinned target above the page, as `DesktopShell` lays it out. */
async function mount(page: Component) {
	const root = document.createElement("div");
	document.body.appendChild(root);

	const app = createApp(
		defineComponent({
			render: () => [
				h("div", { "data-testid": "target" }, [h(PageHeaderTarget)]),
				h("div", { "data-testid": "page" }, [h(page)]),
			],
		})
	);
	app.mount(root);
	mounted.push(app);
	// The target registers on mount, and a deferred teleport moves on the tick after that.
	await nextTick();
	await nextTick();

	return {
		target: root.querySelector<HTMLElement>('[data-testid="target"]')!,
		page: root.querySelector<HTMLElement>('[data-testid="page"]')!,
	};
}

describe("the header row", () => {
	it("teleports the title into the shell's target, out of the page's own tree", async () => {
		const { target, page } = await mount(() => h(PageFrame, { title: "Lead" }, () => "rows"));

		const header = target.querySelector("header");
		expect(header?.textContent).toContain("Lead");
		expect(page.querySelector("header")).toBeNull();
		expect(page.textContent).toContain("rows");
	});

	it("renders the header slot in place of the title", async () => {
		const { target } = await mount(() =>
			h(PageFrame, { title: "Unused" }, { header: () => h("h1", "Leads, mine") })
		);

		const header = target.querySelector("header")!;
		expect(header.textContent).toContain("Leads, mine");
		expect(header.textContent).not.toContain("Unused");
	});

	it("leaves the target empty on a page with nothing for the row", async () => {
		const { target, page } = await mount(() => h(PageFrame, null, () => "body"));

		expect(target.querySelector("header")).toBeNull();
		expect(target.textContent).toBe("");
		expect(page.textContent).toContain("body");
	});
});

describe("the scroll prop", () => {
	it("scrolls the body itself by default, with the gutter on the viewport", async () => {
		const { page } = await mount(() => h(PageFrame, { title: "Home" }, () => "body"));

		const viewport = page.querySelector<HTMLElement>('[data-slot="scroll-area-viewport"]');
		expect(viewport).not.toBeNull();
		for (const cls of pageGutter.split(" ")) expect(viewport!.classList.contains(cls)).toBe(true);
	});

	it("hands the scroll to the page with scroll=false, and applies no gutter", async () => {
		const { page } = await mount(() =>
			h(PageFrame, { title: "Lead", scroll: false }, () => h("p", "body"))
		);

		expect(page.querySelector('[data-slot="scroll-area"]')).toBeNull();
		const pane = page.firstElementChild as HTMLElement;
		expect(pane.className).toContain("overflow-hidden");
		expect(pane.className).not.toContain("px-");
	});
});
