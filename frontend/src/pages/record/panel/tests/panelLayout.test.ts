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

const Assignees = defineComponent({ render: () => h("div", { "data-builtin": "assignees" }) });
const Shares = defineComponent({ render: () => h("div", { "data-builtin": "shares" }) });

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
		{ name: "assignees", component: Assignees },
		{ name: "shares", component: Shares },
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
		expect(names(root)).toEqual(["assignees", "shares", "organization_section"]);
		expect(root.querySelector("[data-builtin='assignees']")).not.toBeNull();
		expect(root.textContent).toContain("Organization");
	});

	it("hides one section by name and its neighbour stands", async () => {
		const surface = new Surface<PanelSectionItem>();
		surface.hide("shares");
		const { root } = await mount(surface);
		expect(names(root)).toEqual(["assignees", "organization_section"]);
		expect(surface.has("assignees")).toBe(true);
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
			{ before: "assignees" }
		);
		surface.move("organization_section", { before: "shares" });
		const { root } = await mount(surface);
		expect(names(root)).toEqual(["note", "assignees", "organization_section", "shares"]);
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

	it("lets a script give a built-in a header by labelling it", async () => {
		const surface = new Surface<PanelSectionItem>();
		surface.update("shares", { label: "Shared with" });
		const { root } = await mount(surface);
		expect(root.querySelectorAll("button[aria-expanded]")).toHaveLength(2);
	});
});
