// The body row: slots for the built-ins, `page` for a script column, separators, edges,
// the narrow-row drop, and a shut column that keeps its content until the width settles.
import { afterEach, describe, expect, it, vi } from "vitest";
import { createApp, defineComponent, h, nextTick } from "vue";
import BodyColumns from "../body/BodyColumns.vue";
import { STORE_KEY } from "../body/columnStore";
import type { BodyItem } from "@/recordPage";

const Column = defineComponent({
	props: { page: Object, tone: String, collapsed: Boolean },
	setup: (props) => () => h("p", `${props.tone}:${props.page?.docname}:${props.collapsed}`),
});

const page = { doctype: "CRM Deal", docname: "D-1" } as any;
const form: BodyItem = { name: "form" };
const panel: BodyItem = { name: "panel", width: 380, minWidth: 320, maxWidth: 640, collapsible: true };
const mounted: ReturnType<typeof createApp>[] = [];

afterEach(() => {
	for (const app of mounted.splice(0)) app.unmount();
	document.body.innerHTML = "";
	localStorage.clear();
	vi.useRealTimers();
});

async function mount(items: BodyItem[], available = 10_000) {
	const root = document.createElement("div");
	document.body.appendChild(root);
	const app = createApp({
		render: () =>
			h(
				BodyColumns,
				{ items, page, user: "tester", available },
				{
					form: () => h("div", { "data-form": "" }, "form"),
					panel: ({ collapsed }: { collapsed: boolean }) =>
						h("div", collapsed ? { "data-strip": "" } : { "data-content": "" }),
				}
			),
	});
	app.mount(root);
	mounted.push(app);
	await nextTick();
	return root;
}

const columns = (root: HTMLElement) => [...root.querySelectorAll<HTMLElement>("[data-body-column]")];
const edges = (root: HTMLElement) => [...root.querySelectorAll<HTMLElement>("[aria-label$='column']")];

describe("BodyColumns", () => {
	it("draws the built-ins from their slots and a script column from its component", async () => {
		const root = await mount([
			{ name: "nav", component: Column, props: { tone: "nav" }, width: 200 },
			form,
			panel,
			{ name: "aside", component: Column, props: { tone: "aside" }, collapsible: true },
		]);
		const names = columns(root).map((el) => el.dataset.bodyColumn);
		expect(names).toEqual(["nav", "form", "panel", "aside"]);
		expect(columns(root)[0].textContent).toBe("nav:D-1:false");
		expect(root.querySelector("[data-form]")).not.toBeNull();
		expect(root.querySelector("[data-content]")).not.toBeNull();
		expect(columns(root)[3].textContent).toBe("aside:D-1:false");
	});

	it("separates neighbours, sizes a fixed column, and lets the flex column grow", async () => {
		const root = await mount([form, panel]);
		const [formColumn, panelColumn] = columns(root);
		expect(formColumn.className).not.toContain("border-l");
		expect(formColumn.className).toContain("flex-1");
		expect(panelColumn.className).toContain("border-l");
		expect(panelColumn.style.width).toBe("380px");
	});

	it("puts one edge on the panel, facing the form, and none on a fixed column with no flex neighbour", async () => {
		const root = await mount([form, panel]);
		const edge = root.querySelector("[aria-label='Collapse panel column']")!;
		expect(edge.parentElement!.previousElementSibling!.getAttribute("data-body-column")).toBe("form");
		expect(edges(await mount([panel])).length).toBe(0);
	});

	it("gives a collapsible flex column a chevron and no drag, and hands it `collapsed`", async () => {
		vi.useFakeTimers();
		const root = await mount([form, panel, { name: "aside", component: Column, collapsible: true }]);
		const chevron = root.querySelector<HTMLButtonElement>("[aria-label='Collapse aside column']")!;
		expect(chevron.parentElement!.querySelector(".cursor-w-resize")).toBeNull();
		chevron.click();
		await nextTick();
		vi.advanceTimersByTime(300);
		await nextTick();
		expect(columns(root)[2].textContent).toBe("undefined:D-1:true");
		expect(columns(root)[2].style.width).toBe("48px");
	});

	it("drops the outside columns on a narrow row and draws the panel as a strip", async () => {
		const root = await mount([{ name: "nav", component: Column, width: 200 }, form, panel], 390);
		expect(columns(root).map((el) => el.dataset.bodyColumn)).toEqual(["form", "panel"]);
		expect(root.querySelector("[data-strip]")).not.toBeNull();
		expect(columns(root)[1].style.width).toBe("48px");
		expect(edges(root).length).toBe(0);
	});

	it("remembers a toggle per user and column, and starts from the memory", async () => {
		const root = await mount([form, panel]);
		root.querySelector<HTMLButtonElement>("[aria-label='Collapse panel column']")!.click();
		await nextTick();
		const stored = JSON.parse(localStorage.getItem(STORE_KEY)!);
		expect(stored.tester.panel).toEqual({ collapsed: true });

		const again = await mount([form, panel]);
		expect(again.querySelector("[data-strip]")).not.toBeNull();
		expect(columns(again)[1].style.width).toBe("48px");
	});
});

function endWidthTransition(root: HTMLElement) {
	const event = new Event("transitionend");
	Object.defineProperty(event, "propertyName", { value: "width" });
	columns(root)[1].dispatchEvent(event);
}

describe("closing", () => {
	it("keeps the content mounted until the width transition ends, then shows the strip", async () => {
		const root = await mount([form, panel]);
		root.querySelector<HTMLButtonElement>("[aria-label='Collapse panel column']")!.click();
		await nextTick();
		expect(root.querySelector("[data-content]")).not.toBeNull();
		expect(root.querySelector("[data-strip]")).toBeNull();
		expect(columns(root)[1].style.width).toBe("48px");

		endWidthTransition(root);
		await nextTick();
		expect(root.querySelector("[data-content]")).toBeNull();
		expect(root.querySelector("[data-strip]")).not.toBeNull();
	});

	it("settles on the timer when no transitionend arrives", async () => {
		vi.useFakeTimers();
		const root = await mount([form, panel]);
		root.querySelector<HTMLButtonElement>("[aria-label='Collapse panel column']")!.click();
		await nextTick();
		expect(root.querySelector("[data-content]")).not.toBeNull();

		vi.advanceTimersByTime(300);
		await nextTick();
		expect(root.querySelector("[data-content]")).toBeNull();
		expect(root.querySelector("[data-strip]")).not.toBeNull();
	});

	it("reopens with the content at once", async () => {
		const root = await mount([form, panel]);
		root.querySelector<HTMLButtonElement>("[aria-label='Collapse panel column']")!.click();
		await nextTick();
		endWidthTransition(root);
		await nextTick();
		expect(root.querySelector("[data-strip]")).not.toBeNull();

		root.querySelector<HTMLButtonElement>("[aria-label='Expand panel column']")!.click();
		await nextTick();
		expect(root.querySelector("[data-content]")).not.toBeNull();
		expect(columns(root)[1].style.width).toBe("380px");
	});
});
