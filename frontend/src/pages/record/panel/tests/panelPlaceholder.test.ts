// A field's own placeholder reads the same at rest and in the open editor; `Add <Label>...` shows
// only when the field has none.
import { afterEach, describe, expect, it, vi } from "vitest";
import { createApp, defineComponent, h, nextTick, ref } from "vue";

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

import { CommitKey, DocKey, NO_COMMIT, ResolveFieldKey, UpdateKey } from "@framework/ui/FormLayout/types";
import type { FieldNode } from "@framework/ui/FormLayout/types";
import PanelField from "../PanelField.vue";

const Control = defineComponent({
	props: { field: Object },
	setup: (props) => () => h("input", { "data-control": "", placeholder: (props.field as any).placeholder }),
});

const mounted: ReturnType<typeof createApp>[] = [];

afterEach(() => {
	for (const app of mounted.splice(0)) app.unmount();
	document.body.innerHTML = "";
});

async function mount(field: Partial<FieldNode>) {
	const root = document.createElement("div");
	document.body.appendChild(root);
	const node = { fieldname: "title", fieldtype: "Data", label: "Title", ...field } as FieldNode;
	const app = createApp(defineComponent({ render: () => h(PanelField, { field: node }) }));
	app.provide(DocKey, ref({ title: "" }));
	app.provide(UpdateKey, vi.fn());
	app.provide(CommitKey, NO_COMMIT);
	app.provide(ResolveFieldKey, () => Control);
	app.mount(root);
	mounted.push(app);
	await nextTick();
	return root;
}

const row = (root: HTMLElement) => root.querySelector<HTMLElement>('[data-fieldname="title"]')!;

async function restAndOpen(root: HTMLElement) {
	const rest = row(root).textContent!.trim();
	row(root).click();
	await nextTick();
	return { rest, open: root.querySelector("[data-control]")!.getAttribute("placeholder") };
}

describe("an empty row's placeholder", () => {
	it("is the field's own at rest and when open", async () => {
		const { rest, open } = await restAndOpen(await mount({ placeholder: "e.g. Annual plan" }));
		expect(rest).toBe("e.g. Annual plan");
		expect(open).toBe("e.g. Annual plan");
	});

	it("is `Add <Label>...` at rest and when open when the field has none", async () => {
		const { rest, open } = await restAndOpen(await mount({}));
		expect(rest).toBe("Add Title...");
		expect(open).toBe("Add Title...");
	});

	it("shows nothing on a read-only row", async () => {
		const root = await mount({ placeholder: "e.g. Annual plan", readOnly: true });
		expect(row(root).textContent!.trim()).toBe("");
	});
});
