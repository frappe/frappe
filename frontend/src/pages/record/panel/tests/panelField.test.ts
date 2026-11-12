// A summary row opens its field on Details, or edits in place when Details does not draw it.
import { afterEach, describe, expect, it, vi } from "vitest";
import { createApp, defineComponent, h, nextTick, ref } from "vue";

vi.mock("frappe-ui", () => ({
	call: vi.fn(),
	toast: { success: vi.fn(), error: vi.fn() },
	createResource: () => ({ data: null, loading: false, fetch() {}, reload() {} }),
	frappeRequest: vi.fn(),
}));
vi.mock("@framework/ui/api", () => ({
	runMethod: vi.fn(async () => ({ data: null })),
	getMeta: vi.fn(async () => ({ data: null })),
}));

import {
	CommitKey,
	ControlPageKey,
	DocKey,
	NO_COMMIT,
	ResolveFieldKey,
	UpdateKey,
} from "@framework/ui/FormLayout/types";
import type { FieldNode } from "@framework/ui/FormLayout/types";
import { FieldErrorsKey } from "@framework/ui/fields/types";
import { PanelContextKey } from "../context";
import PanelField from "../PanelField.vue";

const Control = defineComponent({ render: () => h("textarea", { "data-control": "" }) });

const mounted: ReturnType<typeof createApp>[] = [];

afterEach(() => {
	for (const app of mounted.splice(0)) app.unmount();
	document.body.innerHTML = "";
});

async function mount(
	field: FieldNode,
	onDetails: boolean,
	page?: unknown,
	errors: Record<string, string> = {}
) {
	const expanded: FieldNode[] = [];
	const root = document.createElement("div");
	document.body.appendChild(root);
	const app = createApp(
		defineComponent({
			render: () => h(PanelField, { field, onExpand: (f: FieldNode) => expanded.push(f) }),
		})
	);
	app.provide(DocKey, ref({ settings: '{\n  "a": 1\n}' }));
	app.provide(UpdateKey, vi.fn());
	app.provide(CommitKey, NO_COMMIT);
	app.provide(ResolveFieldKey, () => Control);
	app.provide(PanelContextKey, { onDetails: () => onDetails } as any);
	app.provide(ControlPageKey, ref(page));
	app.provide(FieldErrorsKey, ref(errors));
	app.mount(root);
	mounted.push(app);
	await nextTick();
	return { root, expanded };
}

const json: FieldNode = { fieldname: "settings", fieldtype: "JSON", label: "Settings" };

async function click(root: HTMLElement) {
	root.querySelector<HTMLElement>('[data-fieldname="settings"]')!.click();
	await nextTick();
}

describe("a summary row", () => {
	it("opens the field on Details when Details draws it", async () => {
		const { root, expanded } = await mount(json, true);
		expect(root.querySelector(".lucide-arrow-up-right")).not.toBeNull();
		await click(root);
		expect(expanded.map((f) => f.fieldname)).toEqual(["settings"]);
		expect(root.querySelector("[data-control]")).toBeNull();
	});

	it("edits in place when Details does not draw the field", async () => {
		const { root, expanded } = await mount(json, false);
		expect(root.textContent).toContain("{");
		expect(root.querySelector(".lucide-arrow-up-right")).toBeNull();
		await click(root);
		expect(expanded).toEqual([]);
		expect(root.querySelector("[data-control]")).not.toBeNull();
	});

	it("hands a script's own control the record page as its `page` prop, and a stock control nothing", async () => {
		const Probe = defineComponent({
			props: { page: null },
			setup: (props) => () => h("i", { "data-probe": (props.page as any)?.name ?? "none" }),
		});
		const own: FieldNode = { ...json, ui: { component: Probe } } as FieldNode;
		const scripted = await mount(own, false, { name: "the-page" });
		await click(scripted.root);
		expect(scripted.root.querySelector("[data-probe]")!.getAttribute("data-probe")).toBe("the-page");

		const stock = await mount(json, false, { name: "the-page" });
		await click(stock.root);
		expect(stock.root.querySelector("[data-control]")!.hasAttribute("page")).toBe(false);
	});
});

describe("a script's own control", () => {
	const Probe = defineComponent({ render: () => h("input", { "data-probe": "" }) });
	const scripted = (ui: object): FieldNode =>
		({ ...json, ui: { component: Probe, ...ui } } as FieldNode);

	it("sits in the row box, which draws the hover fill and the focus look on :focus-within", async () => {
		const { root } = await mount(scripted({}), false);
		await click(root);
		const box = root.querySelector("[data-probe]")!.closest<HTMLElement>(".field-box")!;
		expect(box).not.toBeNull();
		expect(box.className).toContain("hover:bg-surface-gray-2");
		expect(box.className).toContain("focus-within:bg-surface-gray-2");
		expect(box.className).toContain("focus-within:ring-outline-gray-3");
	});

	it("draws bare once open with `ownBox`, and keeps the box at rest", async () => {
		const { root } = await mount(scripted({ ownBox: true }), false);
		expect(root.querySelector(".field-box")).not.toBeNull();
		await click(root);
		expect(root.querySelector("[data-probe]")).not.toBeNull();
		expect(root.querySelector(".field-box")).toBeNull();
	});

	it("keeps the box when `ownBox` is set on a stock control", async () => {
		const stock: FieldNode = { ...json, ui: { ownBox: true } } as FieldNode;
		const { root } = await mount(stock, false);
		await click(root);
		expect(root.querySelector("[data-control]")!.closest(".field-box")).not.toBeNull();
	});

	it("still shows the error text under a bare control", async () => {
		const { root } = await mount(scripted({ ownBox: true }), false, undefined, {
			settings: "Bad JSON",
		});
		await click(root);
		expect(root.querySelector(".field-box")).toBeNull();
		expect(root.textContent).toContain("Bad JSON");
	});
});
