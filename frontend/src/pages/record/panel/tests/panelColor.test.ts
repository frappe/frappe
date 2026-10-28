// A panel row shows a Color field's swatch beside its hex, read-only or editable.
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

import {
	CommitKey,
	DocKey,
	NO_COMMIT,
	ResolveFieldKey,
	UpdateKey,
} from "@framework/ui/FormLayout/types";
import type { FieldNode } from "@framework/ui/FormLayout/types";
import PanelField from "../PanelField.vue";

const Control = defineComponent({ render: () => h("input", { "data-control": "" }) });

const mounted: ReturnType<typeof createApp>[] = [];

afterEach(() => {
	for (const app of mounted.splice(0)) app.unmount();
	document.body.innerHTML = "";
});

async function mount(value: string, readOnly = false) {
	const field: FieldNode = { fieldname: "f", fieldtype: "Color", label: "F", readOnly };
	const root = document.createElement("div");
	document.body.appendChild(root);
	const app = createApp(defineComponent({ render: () => h(PanelField, { field }) }));
	app.provide(DocKey, ref({ f: value }));
	app.provide(UpdateKey, vi.fn());
	app.provide(CommitKey, NO_COMMIT);
	app.provide(ResolveFieldKey, () => Control);
	app.mount(root);
	mounted.push(app);
	await nextTick();
	return root;
}

describe("a panel row for a Color field", () => {
	it.each([false, true])("draws the swatch and the hex (read-only %s)", async (readOnly) => {
		const root = await mount("#ce2c2c", readOnly);
		const swatch = root.querySelector<HTMLElement>("[data-slot='swatch']");
		expect(swatch?.style.backgroundColor).toBeTruthy();
		expect(root.querySelector("[data-fieldname='f']")?.textContent?.trim()).toBe("#ce2c2c");
	});

	it("draws no swatch when empty", async () => {
		const root = await mount("");
		expect(root.querySelector("[data-slot='swatch']")).toBeNull();
	});
});
