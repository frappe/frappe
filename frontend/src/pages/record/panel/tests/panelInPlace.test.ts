// Check, Rating, Color and Attach act on one click in the box: no editor opens, no Esc undo.
import { afterEach, describe, expect, it, vi } from "vitest";
import { createApp, defineComponent, h, nextTick, ref } from "vue";

vi.mock("@framework/ui/api", () => ({
	runMethod: vi.fn(async () => ({ data: null })),
	getMeta: vi.fn(async () => ({ data: null })),
}));

import { getFieldComponent } from "@framework/ui/fields";
import {
	CommitKey,
	DocKey,
	ResolveFieldKey,
	UpdateKey,
} from "@framework/ui/FormLayout/types";
import type { FieldNode } from "@framework/ui/FormLayout/types";
import { PanelContextKey, PanelFieldsKey } from "../context";
import PanelField from "../PanelField.vue";

const mounted: ReturnType<typeof createApp>[] = [];

afterEach(() => {
	for (const app of mounted.splice(0)) app.unmount();
	document.body.innerHTML = "";
});

async function mount(
	field: FieldNode,
	values: Record<string, any>,
	options: { expanded?: FieldNode[]; panelFields?: string[] } = {}
) {
	const commits: [string, unknown][] = [];
	const doc = ref(values);
	const root = document.createElement("div");
	document.body.appendChild(root);
	const app = createApp(
		defineComponent({
			render: () =>
				h(PanelField, {
					field,
					onExpand: (f: FieldNode) => options.expanded?.push(f),
				}),
		})
	);
	app.provide(DocKey, doc);
	app.provide(UpdateKey, (name: string, value: unknown) => (doc.value[name] = value));
	app.provide(CommitKey, {
		pending: () => {},
		discard: () => {},
		commit: (name: string, value: unknown) => commits.push([name, value]),
		rowChanged: () => {},
	});
	app.provide(ResolveFieldKey, getFieldComponent);
	app.provide(PanelContextKey, { onDetails: () => true } as any);
	app.provide(PanelFieldsKey, ref(new Set(options.panelFields ?? [])));
	app.mount(root);
	mounted.push(app);
	await nextTick();
	return { root, commits, doc };
}

const cell = (root: HTMLElement) => root.querySelector<HTMLElement>("[data-fieldname]")!;

describe("Check", () => {
	const field: FieldNode = { fieldname: "c", fieldtype: "Check", label: "Active" };

	it("draws the checkbox at rest, not Yes or No", async () => {
		const { root } = await mount(field, { c: 1 });
		expect(root.querySelector<HTMLInputElement>("input[type=checkbox]")?.checked).toBe(true);
		expect(root.textContent).not.toMatch(/Yes|No/);
	});

	it("toggles and commits once on a click on the box", async () => {
		const { root, commits } = await mount(field, { c: 0 });
		root.querySelector<HTMLElement>("[data-fieldname] > div")!.click();
		expect(commits).toEqual([["c", 1]]);
	});

	it("toggles and commits once on a click on the checkbox", async () => {
		const { root, commits } = await mount(field, { c: 1 });
		root.querySelector<HTMLInputElement>("input")!.click();
		await nextTick();
		expect(commits).toEqual([["c", 0]]);
	});

	it("draws a disabled checkbox when read-only and ignores a click", async () => {
		const { root, commits } = await mount({ ...field, readOnly: true }, { c: 1 });
		expect(root.querySelector<HTMLInputElement>("input")?.disabled).toBe(true);
		root.querySelector<HTMLElement>("[data-fieldname] > div")!.click();
		expect(commits).toEqual([]);
	});

	it("keeps no label, description or error text of its own", async () => {
		const { root } = await mount(
			{ ...field, description: "Help text" },
			{ c: 0 }
		);
		expect(root.querySelectorAll("label")).toHaveLength(0);
		expect(root.textContent).not.toContain("Help text");
	});
});

describe("Rating", () => {
	const field: FieldNode = { fieldname: "r", fieldtype: "Rating", label: "Score", options: "5" };

	it("draws the stars at rest, not 3 / 5", async () => {
		const { root } = await mount(field, { r: 0.6 });
		expect(root.querySelectorAll("[data-slot=star]")).toHaveLength(5);
		expect(root.textContent).not.toContain("/ 5");
	});

	it("saves the fraction on a click on a star", async () => {
		const { root, commits } = await mount(field, { r: 0 });
		root.querySelectorAll<HTMLElement>("[data-slot=star]")[3].click();
		expect(commits).toHaveLength(1);
		expect(commits[0][0]).toBe("r");
		expect(commits[0][1]).toBeCloseTo(0.8, 1);
	});

	it("mutes the stars and saves nothing when read-only", async () => {
		const { root, commits } = await mount({ ...field, readOnly: true }, { r: 0.6 });
		expect(cell(root).firstElementChild?.className).toContain("opacity-50");
		root.querySelectorAll<HTMLElement>("[data-slot=star]")[3].click();
		expect(commits).toEqual([]);
	});
});

describe("Color", () => {
	const field: FieldNode = { fieldname: "k", fieldtype: "Color", label: "Color" };

	it("keeps the swatch before the hex, with an 8px gap", async () => {
		const { root } = await mount(field, { k: "#3b82f6" });
		const trigger = root.querySelector("button[data-slot=control]")!;
		expect(trigger.className).toContain("gap-2");
		expect(trigger.firstElementChild?.getAttribute("data-slot")).toBe("swatch");
		expect(trigger.textContent?.trim()).toBe("#3b82f6");
	});

	it("reads Add Color... when empty", async () => {
		const { root } = await mount(field, { k: "" });
		expect(root.querySelector("button[data-slot=control]")?.textContent?.trim()).toBe(
			"Add Color..."
		);
	});
});

describe("Attach", () => {
	const field: FieldNode = { fieldname: "a", fieldtype: "Attach", label: "File" };

	it("reads Add File... when empty and does not expand to Details", async () => {
		const expanded: FieldNode[] = [];
		const { root } = await mount(field, { a: "" }, { expanded });
		const button = root.querySelector<HTMLElement>("button[data-slot=control]")!;
		expect(button.textContent?.trim()).toBe("Add File...");
		button.click();
		expect(expanded).toEqual([]);
	});

	it("shows the file name with ↗ and × when filled, and × clears", async () => {
		const { root, commits } = await mount(field, { a: "/files/report%20one.pdf" });
		expect(root.querySelector("button[data-slot=control]")?.textContent?.trim()).toBe(
			"report one.pdf"
		);
		expect(root.querySelector("a[href='/files/report%20one.pdf']")).not.toBeNull();
		root.querySelector<HTMLElement>("button[data-slot=clear]")!.click();
		expect(commits).toEqual([["a", null]]);
	});

	it("keeps the ↗ to Details for a field a script gave its own control", async () => {
		const expanded: FieldNode[] = [];
		const ui = { component: defineComponent({ render: () => h("span") }) };
		const { root } = await mount({ ...field, ui }, { a: "" }, { expanded });
		cell(root).click();
		expect(expanded).toEqual([{ ...field, ui }]);
	});

	it("draws ↗ but no × when read-only", async () => {
		const { root } = await mount({ ...field, readOnly: true }, { a: "/files/a.pdf" });
		expect(root.querySelector("a[href='/files/a.pdf']")).not.toBeNull();
		expect(root.querySelector("button[data-slot=clear]")).toBeNull();
	});

	it("shows a 20px thumbnail before the name for an Attach Image", async () => {
		const { root } = await mount(
			{ ...field, fieldtype: "Attach Image" },
			{ a: "/files/photo.png" }
		);
		const image = root.querySelector("button[data-slot=control] img")!;
		expect(image.className).toContain("size-5");
		expect(image.nextElementSibling?.textContent?.trim()).toBe("photo.png");
	});
});

describe("Image", () => {
	const field: FieldNode = {
		fieldname: "pic",
		fieldtype: "Image",
		label: "Picture",
		options: "photo",
		readOnly: true,
	};

	it("is hidden when the panel draws the Attach Image it reads", async () => {
		const { root } = await mount(field, { photo: "/files/p.png" }, { panelFields: ["photo"] });
		expect(root.querySelector("[data-fieldname]")).toBeNull();
	});

	it("previews from the keyboard too", async () => {
		const { root } = await mount(field, { photo: "/files/p.png" });
		expect(cell(root).getAttribute("role")).toBe("button");
		cell(root).dispatchEvent(new KeyboardEvent("keydown", { key: "Enter", bubbles: true }));
		await nextTick();
		await nextTick();
		expect(document.querySelector("[role=dialog] img")).not.toBeNull();
	});

	it("shows a 20px thumbnail and the file name otherwise, and a click previews it", async () => {
		const expanded: FieldNode[] = [];
		const { root } = await mount(field, { photo: "/files/p.png" }, { expanded });
		const image = cell(root).querySelector("img")!;
		expect(image.className).toContain("size-5");
		expect(cell(root).textContent?.trim()).toBe("p.png");
		cell(root).click();
		await nextTick();
		await nextTick();
		expect(expanded).toEqual([]);
		expect(document.querySelector("[role=dialog] img")?.getAttribute("src")).toBe(
			"/files/p.png"
		);
	});
});
