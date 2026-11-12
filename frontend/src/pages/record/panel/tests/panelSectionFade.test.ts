// The fade under a pinned section header grows with the rows scrolled beneath it.
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

async function mountSection() {
	const scroller = document.createElement("div");
	scroller.style.overflowY = "auto";
	document.body.appendChild(scroller);
	const app = createApp(
		defineComponent({
			render: () =>
				h(
					PanelSection,
					{ name: "fields_b", label: "Fields B", fields: [], index: 1, headerIndex: 0, open: true, pinTop: 0 },
					{ default: () => h("p", "row") }
				),
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

describe("the pinned header's fade", () => {
	const fadeOf = (header: HTMLElement) => header.style.getPropertyValue("--fade");

	it("is drawn at no height while the rows start below the header", async () => {
		const { header, scrollTo } = await mountSection();
		await scrollTo(42);
		expect(fadeOf(header)).toBe("0px");
	});

	it("grows with the rows scrolled under the header, up to 24px, and goes when they scroll back", async () => {
		const { header, scrollTo } = await mountSection();
		await scrollTo(33);
		expect(fadeOf(header)).toBe("9px");
		await scrollTo(-200);
		expect(fadeOf(header)).toBe("24px");
		await scrollTo(50);
		expect(fadeOf(header)).toBe("0px");
	});
});
