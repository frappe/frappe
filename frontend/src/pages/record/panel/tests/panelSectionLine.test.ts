// A pinned section header draws a line along its bottom edge only while rows are beneath it.
import { afterEach, describe, expect, it, vi } from "vitest";
import { createApp, defineComponent, h, nextTick } from "vue";

vi.mock("frappe-ui", async (importOriginal) => ({
	...((await importOriginal()) as Record<string, unknown>),
	call: vi.fn(),
	toast: { success: vi.fn(), error: vi.fn() },
	createResource: () => ({ data: null, loading: false, fetch() {}, reload() {} }),
	frappeRequest: vi.fn(),
}));
vi.mock("@framework/ui/api", () => ({
	runMethod: vi.fn(async () => ({ data: null })),
	getMeta: vi.fn(async () => ({ data: null })),
}));

import PanelSection from "../PanelSection.vue";

const mounted: ReturnType<typeof createApp>[] = [];

afterEach(() => {
	for (const app of mounted.splice(0)) app.unmount();
	document.body.innerHTML = "";
});

function stubTop(element: Element, top: number) {
	element.getBoundingClientRect = () => ({ top, bottom: top + 42 }) as DOMRect;
}

async function mountSection(open = true) {
	const scroller = document.createElement("div");
	scroller.style.overflowY = "auto";
	document.body.appendChild(scroller);
	const app = createApp(
		defineComponent({
			render: () => [
				h(
					PanelSection,
					{ name: "fields_b", label: "Fields B", fields: [], index: 1, headerIndex: 0, open, pinTop: 0 },
					{ default: () => h("p", "row") }
				),
				h("p", "the next section"),
			],
		})
	);
	mounted.push(app);
	app.mount(scroller);
	await nextTick();
	const header = scroller.querySelector<HTMLElement>("div.sticky")!;
	const body = header.nextElementSibling as HTMLElement;
	const scrollTo = async (bodyTop: number) => {
		stubTop(header, 0);
		stubTop(body, bodyTop);
		scroller.dispatchEvent(new Event("scroll"));
		await nextTick();
	};
	return { header, scrollTo };
}

describe("the pinned header's line", () => {
	const lined = (header: HTMLElement) => header.classList.contains("after:border-outline-gray-1");

	it("is not drawn while the rows start below the header", async () => {
		const { header, scrollTo } = await mountSection();
		await scrollTo(42);
		expect(lined(header)).toBe(false);
	});

	it("shows, 1px high and with no fade, while rows are under the header, and goes when they scroll back", async () => {
		const { header, scrollTo } = await mountSection();
		await scrollTo(41);
		expect(lined(header)).toBe(true);
		expect(header.classList.contains("after:h-px")).toBe(true);
		expect(header.className).not.toContain("gradient");
		await scrollTo(-200);
		expect(lined(header)).toBe(true);
		await scrollTo(50);
		expect(lined(header)).toBe(false);
	});

	it("is not drawn for a sub-pixel overlap", async () => {
		const { header, scrollTo } = await mountSection();
		await scrollTo(41.5);
		expect(lined(header)).toBe(false);
	});

	it("shows while the next section scrolls under a collapsed header", async () => {
		const { header, scrollTo } = await mountSection(false);
		expect(header.nextElementSibling!.textContent).toBe("the next section");
		await scrollTo(30);
		expect(lined(header)).toBe(true);
	});
});
