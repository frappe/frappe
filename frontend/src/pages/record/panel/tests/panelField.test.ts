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
	DocKey,
	NO_COMMIT,
	ResolveFieldKey,
	UpdateKey,
} from "@framework/ui/FormLayout/types";
import type { FieldNode } from "@framework/ui/FormLayout/types";
import { PanelContextKey } from "../context";
import PanelField from "../PanelField.vue";

const Control = defineComponent({ render: () => h("textarea", { "data-control": "" }) });

const mounted: ReturnType<typeof createApp>[] = [];

afterEach(() => {
	for (const app of mounted.splice(0)) app.unmount();
	document.body.innerHTML = "";
});

async function mount(field: FieldNode, onDetails: boolean) {
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
});
