// A marked panel row at rest: the value in red with the message on one line under it, and
// the editor a click opens passes the error to its control.
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

import { FieldErrorsKey } from "@framework/ui/components/Fields/types";
import {
	CommitKey,
	DocKey,
	NO_COMMIT,
	ResolveFieldKey,
	UpdateKey,
} from "@framework/ui/components/FormLayout/types";
import type { FieldNode } from "@framework/ui/components/FormLayout/types";
import PanelField from "../PanelField.vue";

const Control = defineComponent({
	props: { error: [String, Array] },
	setup: (props) => () => h("input", { "data-control": "", "data-error": props.error }),
});

const mounted: ReturnType<typeof createApp>[] = [];

afterEach(() => {
	for (const app of mounted.splice(0)) app.unmount();
	document.body.innerHTML = "";
});

const qty: FieldNode = { fieldname: "qty", fieldtype: "Int", label: "Qty" };

async function mount(errors: Record<string, string>) {
	const root = document.createElement("div");
	document.body.appendChild(root);
	const app = createApp(defineComponent({ render: () => h(PanelField, { field: qty }) }));
	app.provide(DocKey, ref({ qty: -2 }));
	app.provide(UpdateKey, vi.fn());
	app.provide(CommitKey, NO_COMMIT);
	app.provide(ResolveFieldKey, () => Control);
	app.provide(FieldErrorsKey, ref(errors));
	app.mount(root);
	mounted.push(app);
	await nextTick();
	return root;
}

describe("a marked panel row", () => {
	it("shows the value in red and the message on one line, with the full text in its title", async () => {
		const root = await mount({ qty: "Quantity must be positive" });
		const row = root.querySelector<HTMLElement>('[data-fieldname="qty"]')!;
		const [value, message] = row.querySelectorAll("span");

		expect(value.className).toContain("text-ink-red-4");
		expect(message.textContent!.trim()).toBe("Quantity must be positive");
		expect(message.className).toContain("truncate");
		expect(message.title).toBe("Quantity must be positive");
	});

	it("passes the error to the control a click opens", async () => {
		const root = await mount({ qty: "Quantity must be positive" });

		root.querySelector<HTMLElement>('[data-fieldname="qty"]')!.click();
		await nextTick();

		expect(root.querySelector("[data-control]")!.getAttribute("data-error")).toBe(
			"Quantity must be positive"
		);
	});

	it("draws no message on an unmarked row", async () => {
		const root = await mount({});
		const row = root.querySelector<HTMLElement>('[data-fieldname="qty"]')!;

		expect(row.querySelectorAll("span")).toHaveLength(1);
		expect(row.querySelector("span")!.className).not.toContain("text-ink-red-4");
	});
});
