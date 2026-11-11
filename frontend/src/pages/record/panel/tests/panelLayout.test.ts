// The renderer over `page.panelSections`: one list, a header only where there is a label,
// and the proof walk's second act: hide one section by name, its neighbour stands.
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { createApp, defineComponent, h, nextTick, ref } from "vue";

vi.mock("frappe-ui", async (importOriginal) => ({
	...((await importOriginal()) as Record<string, unknown>),
	call: vi.fn(),
	toast: { success: vi.fn(), error: vi.fn() },
	createResource: () => ({ data: null, loading: false, fetch() {}, reload() {} }),
	frappeRequest: vi.fn(),
}));
const catalog = vi.hoisted(() => ({ messages: {} as Record<string, string> }));

vi.mock("@framework/ui/api", () => ({
	runMethod: vi.fn(async () => ({ data: null })),
	getMeta: vi.fn(async () => ({ data: null })),
	getTranslations: vi.fn(async () => ({ data: catalog.messages })),
}));

import type { FormLayoutSchema } from "@framework/ui/FormLayout/types";
import { CommitKey, NO_COMMIT } from "@framework/ui/FormLayout/types";
import { loadTranslations } from "@/i18n";
import { Surface } from "@/pageEngine/surface";
import type { PanelSectionItem } from "@/recordPage";
import PanelLayout from "../PanelLayout.vue";
import { layoutItems, layoutSections } from "../panelEntries";

const field = (fieldname: string) => ({ fieldname, fieldtype: "Data", label: fieldname });

const LAYOUT: FormLayoutSchema = [
	{
		name: "main",
		sections: [
			{
				name: "organization_section",
				label: "Organization",
				columns: [{ fields: [field("organization")] }],
			},
		],
	},
] as any;

const Identity = defineComponent({
	render() {
		return h("div", { "data-builtin": "identity" }, this.$slots.default?.());
	},
});
const QuickActions = defineComponent({
	render: () => h("div", { "data-builtin": "quick_actions" }),
});
const People = defineComponent({ render: () => h("div", { "data-builtin": "people" }) });
const Note = defineComponent({
	props: { text: String },
	render() {
		return h("p", { "data-note": this.text });
	},
});

const mounted: ReturnType<typeof createApp>[] = [];

afterEach(() => {
	for (const app of mounted.splice(0)) app.unmount();
	document.body.innerHTML = "";
});

beforeEach(() => {
	vi.spyOn(console, "warn").mockImplementation(() => {});
});

async function mount(
	surface: Surface<PanelSectionItem>,
	opened: Record<string, boolean> = {},
	doctype?: string,
	scrolls = false,
	layout: FormLayoutSchema = LAYOUT
) {
	const doc = ref({ organization: "Frappe" });
	const sections = layoutSections(layout, doc.value);
	surface.provideBuiltins(() => [
		{ name: "identity", component: Identity },
		{ name: "quick_actions", component: QuickActions },
		{ name: "people", component: People },
		...layoutItems(sections),
	]);
	const toggled: string[] = [];
	const root = document.createElement("div");
	if (scrolls) root.style.overflowY = "auto";
	document.body.appendChild(root);
	const app = createApp(
		defineComponent({
			render: () =>
				h(PanelLayout, {
					surface,
					sections,
					doctype,
					page: { doc: doc.value } as any,
					doc: doc.value,
					isOpen: (name: string) => opened[name] ?? true,
					onToggle: (name: string) => toggled.push(name),
				}),
		})
	);
	app.provide(CommitKey, NO_COMMIT);
	app.mount(root);
	mounted.push(app);
	await nextTick();
	return { root, toggled };
}

const names = (root: HTMLElement) =>
	[...root.querySelectorAll<HTMLElement>("[data-section]")].map((el) => el.dataset.section);

describe("an Image row beside its Attach Image", () => {
	const column = (...fields: any[]) => [{ fields }];
	const photo = { fieldname: "photo", fieldtype: "Attach Image", label: "Photo" };
	const shown = { fieldname: "pic", fieldtype: "Image", label: "Pic", options: "photo" };

	it("leaves no empty section when it was the only field of its own", async () => {
		const layout = [
			{
				name: "main",
				sections: [
					{ name: "a", label: "A", columns: column(photo) },
					{ name: "b", label: "B", columns: column(shown) },
				],
			},
		] as any;
		const { root } = await mount(new Surface<PanelSectionItem>(), {}, undefined, false, layout);
		expect(names(root)).toContain("a");
		expect(names(root)).not.toContain("b");
	});
});

describe("one list", () => {
	it("draws the built-ins and the layout's sections in the surface's order", async () => {
		const { root } = await mount(new Surface<PanelSectionItem>());
		expect(names(root)).toEqual(["identity", "people", "organization_section"]);
		expect(root.querySelector("[data-builtin='identity']")).not.toBeNull();
		expect(root.textContent).toContain("Organization");
	});

	it("draws a divider above every item after the first, headerless or not", async () => {
		const { root } = await mount(new Surface<PanelSectionItem>());
		const bodies = [...root.querySelectorAll<HTMLElement>("[data-section]")];
		expect(bodies.map((el) => el.classList.contains("border-t"))).toEqual([false, true, true]);
	});

	it("draws the quick actions inside the identity, and apart once moved off it", async () => {
		const embedded = await mount(new Surface<PanelSectionItem>());
		expect(
			embedded.root.querySelector("[data-builtin='identity'] [data-builtin='quick_actions']")
		).not.toBeNull();

		const surface = new Surface<PanelSectionItem>();
		surface.move("quick_actions", { after: "people" });
		const moved = await mount(surface);
		expect(names(moved.root)).toEqual([
			"identity",
			"people",
			"quick_actions",
			"organization_section",
		]);
		const apart = moved.root.querySelector<HTMLElement>("[data-section='quick_actions']")!;
		expect(apart.classList.contains("border-t")).toBe(true);
		expect(apart.querySelector("[data-builtin='quick_actions']")).not.toBeNull();
	});

	it("keeps the quick actions a section of their own once a script gives them a header", async () => {
		const surface = new Surface<PanelSectionItem>();
		surface.update("quick_actions", { label: "Actions" });
		const { root } = await mount(surface);
		expect(root.querySelector("[data-builtin='identity'] [data-builtin='quick_actions']")).toBeNull();
		expect(root.textContent).toContain("Actions");
		expect(root.querySelector("[data-builtin='quick_actions']")).not.toBeNull();
	});

	it("hides one section by name and its neighbour stands", async () => {
		const surface = new Surface<PanelSectionItem>();
		surface.hide("people");
		const { root } = await mount(surface);
		expect(names(root)).toEqual(["identity", "organization_section"]);
		expect(surface.has("identity")).toBe(true);
	});

	it("moves a layout section among the built-ins, and a script's section renders its component", async () => {
		const surface = new Surface<PanelSectionItem>();
		surface.add(
			{
				name: "note",
				label: "Note",
				component: defineComponent({
					props: { page: Object, text: String },
					render() {
						return h("div", { "data-note": this.text }, this.page?.doc?.organization);
					},
				}),
				props: { text: "hi" },
			},
			{ before: "identity" }
		);
		surface.move("organization_section", { before: "people" });
		const { root } = await mount(surface);
		expect(names(root)).toEqual(["note", "identity", "organization_section", "people"]);
		const note = root.querySelector<HTMLElement>("[data-note]")!;
		expect(note.dataset.note).toBe("hi");
		expect(note.textContent).toBe("Frappe");
	});
});

describe("the leading built-ins stay in view", () => {
	afterEach(() => vi.unstubAllGlobals());

	// jsdom lays nothing out: report the pinned block's height and the column's.
	async function sized(heights: { block: number; column: number }) {
		vi.stubGlobal(
			"ResizeObserver",
			class {
				constructor(private callback: ResizeObserverCallback) {}
				observe(el: HTMLElement) {
					const blockSize = el.dataset.panelPinned ? heights.block : heights.column;
					const box = [{ blockSize, inlineSize: 0 }];
					const entry = { target: el, borderBoxSize: box, contentBoxSize: box };
					queueMicrotask(() => this.callback([entry as any], this as any));
				}
				unobserve() {}
				disconnect() {}
			}
		);
		const mounted = await mount(new Surface<PanelSectionItem>(), {}, undefined, true);
		await new Promise((resolve) => setTimeout(resolve));
		return mounted;
	}

	const pinnedNames = (root: HTMLElement) =>
		names(root.querySelector<HTMLElement>("[data-panel-pinned]") ?? document.createElement("div"));

	it("pins the identity, its quick actions and the people, and scrolls the layout's sections", async () => {
		const { root } = await mount(new Surface<PanelSectionItem>());
		const pinned = root.querySelector<HTMLElement>("[data-panel-pinned]")!;
		expect(names(pinned)).toEqual(["identity", "people"]);
		expect(pinned.querySelector("[data-builtin='quick_actions']")).not.toBeNull();
		expect(pinned.nextElementSibling!.querySelector("[data-section='organization_section']")).not.toBeNull();
	});

	it("pins the block when it takes at most half the column, and the headers below it", async () => {
		const { root } = await sized({ block: 200, column: 400 });
		expect(root.querySelector("[data-panel-pinned]")!.classList.contains("sticky")).toBe(true);
		const header = root.querySelector<HTMLElement>("[data-section='organization_section']")!;
		expect(header.style.top).toBe("200px");
	});

	it("lets the block scroll on a column too short for it", async () => {
		const { root } = await sized({ block: 200, column: 399 });
		expect(root.querySelector("[data-panel-pinned]")!.classList.contains("sticky")).toBe(false);
		const header = root.querySelector<HTMLElement>("[data-section='organization_section']")!;
		expect(header.style.top).toBe("0px");
	});

	it("lets a built-in a script moved below a section scroll", async () => {
		const surface = new Surface<PanelSectionItem>();
		surface.move("people", { after: "organization_section" });
		const { root } = await mount(surface);
		expect(pinnedNames(root)).toEqual(["identity"]);
	});

	it("ends the run at a labelled built-in or a script's item", async () => {
		const labelled = new Surface<PanelSectionItem>();
		labelled.update("people", { label: "People" });
		expect(pinnedNames((await mount(labelled)).root)).toEqual(["identity"]);

		const added = new Surface<PanelSectionItem>();
		added.add({ name: "note", component: Note, props: { text: "hi" } }, { before: "identity" });
		const { root } = await mount(added);
		expect(root.querySelector("[data-panel-pinned]")).toBeNull();
	});
});

describe("a header comes from a label", () => {
	it("gives a labelled section a chevron and a built-in none", async () => {
		const { root, toggled } = await mount(new Surface<PanelSectionItem>());
		const headers = root.querySelectorAll("button[aria-expanded]");
		expect(headers).toHaveLength(1);
		expect(headers[0].textContent).toContain("Organization");
		(headers[0] as HTMLButtonElement).click();
		expect(toggled).toEqual(["organization_section"]);
	});

	it("keeps a shut section's header and drops its fields", async () => {
		const { root } = await mount(new Surface<PanelSectionItem>(), {
			organization_section: false,
		});
		expect(root.querySelector("button[aria-expanded]")?.getAttribute("aria-expanded")).toBe("false");
		expect(root.querySelector("[data-fieldname='organization']")).toBeNull();
	});

	it("pads a body less at the top under a header than without one", async () => {
		const { root } = await mount(new Surface<PanelSectionItem>());
		const headed = root.querySelector("[data-section='organization_section']")!.nextElementSibling!;
		expect(headed.classList.contains("pt-1")).toBe(true);
		expect(headed.classList.contains("pb-3")).toBe(true);
		expect(headed.classList.contains("py-3")).toBe(false);
		const headerless = root.querySelector("[data-section='people']")!;
		expect(headerless.classList.contains("py-3")).toBe(true);
	});

	it("lets a script give a built-in a header by labelling it", async () => {
		const surface = new Surface<PanelSectionItem>();
		surface.update("people", { label: "People" });
		const { root } = await mount(surface);
		expect(root.querySelectorAll("button[aria-expanded]")).toHaveLength(2);
	});
});

describe("a header can carry actions", () => {
	const Actions = defineComponent({
		props: { page: Object, text: String },
		render() {
			return h("button", { "data-actions": this.text ?? "" }, this.page?.doc?.organization);
		},
	});

	function withActions(surface = new Surface<PanelSectionItem>()) {
		surface.add(
			{ name: "note", label: "Note", component: Note, props: { text: "hi" }, actions: Actions },
			{ before: "people" }
		);
		return surface;
	}

	it("draws them in the header with the section's props and the page, open or shut", async () => {
		for (const open of [true, false]) {
			const { root } = await mount(withActions(), { note: open });
			const header = root.querySelector<HTMLElement>("[data-section='note']")!;
			const actions = header.querySelector<HTMLElement>("[data-actions]")!;
			expect(actions.dataset.actions).toBe("hi");
			expect(actions.textContent).toBe("Frappe");
			expect(header.querySelector("button[aria-expanded]")!.getAttribute("aria-expanded")).toBe(
				String(open)
			);
		}
	});

	it("does not toggle the section on a click on them, as the header around them does", async () => {
		const { root, toggled } = await mount(withActions());
		root.querySelector<HTMLElement>("[data-actions]")!.click();
		expect(toggled).toEqual([]);
		root.querySelector<HTMLElement>("[data-section='note']")!.click();
		expect(toggled).toEqual(["note"]);
	});

	it("draws them on a layout section a script updates, with the page", async () => {
		const surface = new Surface<PanelSectionItem>();
		surface.update("organization_section", { actions: Actions });
		const { root } = await mount(surface);
		const header = root.querySelector<HTMLElement>("[data-section='organization_section']")!;
		expect(header.querySelector("[data-actions]")!.textContent).toBe("Frappe");
	});

	it("draws no actions slot on a header without them", async () => {
		const { root } = await mount(new Surface<PanelSectionItem>());
		const header = root.querySelector<HTMLElement>("[data-section='organization_section']")!;
		expect(header.children).toHaveLength(1);
	});
});

describe("a header translates with the DocType as context", () => {
	afterEach(async () => {
		catalog.messages = {};
		await loadTranslations("reset", "en");
	});

	it("draws the label from the catalog, else the text without context", async () => {
		catalog.messages = { "Organization:Contact": "Organisation" };
		await loadTranslations("test", "fr");

		const contact = await mount(new Surface<PanelSectionItem>(), {}, "Contact");
		expect(contact.root.textContent).toContain("Organisation");

		const lead = await mount(new Surface<PanelSectionItem>(), {}, "Lead");
		expect(lead.root.textContent).not.toContain("Organisation");
		expect(lead.root.textContent).toContain("Organization");
	});
});
