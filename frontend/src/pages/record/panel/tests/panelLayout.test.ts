// The renderer over `page.panelSections`: one list, a header only where there is a label,
// and the proof walk's second act: hide one section by name, its neighbour stands.
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { createApp, defineComponent, h, nextTick, ref } from "vue";

vi.mock("frappe-ui", () => ({
	call: vi.fn(),
	toast: { success: vi.fn(), error: vi.fn() },
	createResource: () => ({ data: null, loading: false, fetch() {}, reload() {} }),
	frappeRequest: vi.fn(),
}));

import type { FormLayoutSchema } from "@framework/ui/components/FormLayout/types";
import { CommitKey, NO_COMMIT } from "@framework/ui/components/FormLayout/types";
import { Surface } from "@/recordPage/surface";
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

const mounted: ReturnType<typeof createApp>[] = [];

afterEach(() => {
	for (const app of mounted.splice(0)) app.unmount();
	document.body.innerHTML = "";
});

beforeEach(() => {
	vi.spyOn(console, "warn").mockImplementation(() => {});
});

async function mount(surface: Surface<PanelSectionItem>, opened: Record<string, boolean> = {}) {
	const doc = ref({ organization: "Frappe" });
	const sections = layoutSections(LAYOUT, doc.value);
	surface.provideBuiltins(() => [
		{ name: "identity", component: Identity },
		{ name: "quick_actions", component: QuickActions },
		{ name: "people", component: People },
		...layoutItems(sections),
	]);
	const toggled: string[] = [];
	const root = document.createElement("div");
	document.body.appendChild(root);
	const app = createApp(
		defineComponent({
			render: () =>
				h(PanelLayout, {
					surface,
					sections,
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
