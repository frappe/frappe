// A marked panel row: the value in red, the message on two lines at most under its box, the red
// focus ring, and the control the row opens pointing at the message.
import { afterEach, describe, expect, it, vi } from "vitest";
import { createApp, defineComponent, h, isRef, nextTick, ref } from "vue";
import type { Ref } from "vue";

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

import { FieldErrorsKey } from "@framework/ui/fields/types";
import {
	CommitKey,
	DocKey,
	NO_COMMIT,
	ResolveFieldKey,
	UpdateKey,
} from "@framework/ui/FormLayout/types";
import type { FieldNode } from "@framework/ui/FormLayout/types";
import { FieldErrors } from "@/recordPage/fieldErrors";
import PanelField from "../PanelField.vue";

const Control = defineComponent({
	props: { error: [String, Array], errorId: String },
	setup: (props) => () =>
		h("input", { "data-control": "", "data-error": props.error, "aria-describedby": props.errorId }),
});

const mounted: ReturnType<typeof createApp>[] = [];

afterEach(() => {
	for (const app of mounted.splice(0)) app.unmount();
	document.body.innerHTML = "";
});

const qty: FieldNode = { fieldname: "qty", fieldtype: "Int", label: "Qty" };

async function mount(errors: Record<string, string> | Ref<Record<string, any>>, fieldtype = "Int") {
	const root = document.createElement("div");
	document.body.appendChild(root);
	const app = createApp(defineComponent({ render: () => h(PanelField, { field: { ...qty, fieldtype } }) }));
	app.provide(DocKey, ref({ qty: -2 }));
	app.provide(UpdateKey, vi.fn());
	app.provide(CommitKey, NO_COMMIT);
	app.provide(ResolveFieldKey, () => Control);
	app.provide(FieldErrorsKey, isRef(errors) ? errors : ref(errors));
	app.mount(root);
	mounted.push(app);
	await nextTick();
	return root;
}

describe("a marked panel row", () => {
	it("shows the value in red and the message on two lines at most, with the full text in its title", async () => {
		const root = await mount({ qty: "Quantity must be positive" });
		const row = root.querySelector<HTMLElement>('[data-fieldname="qty"]')!;
		const value = row.querySelector("span")!;
		const message = root.querySelector<HTMLElement>("span.text-sm[title]")!;

		expect(value.className).toContain("text-ink-red-6");
		expect(message.textContent!.trim()).toBe("Quantity must be positive");
		expect(message.className).toContain("line-clamp-2");
		expect(message.className).not.toContain("truncate");
		// `block` would override line-clamp's display and show every line.
		expect(message.className).not.toContain("block");
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

		expect(root.querySelector("span.text-sm[title]")).toBeNull();
		expect(row.querySelector("span")!.className).not.toContain("text-ink-red-6");
	});

	it("draws the red ring on the box while it holds the message", async () => {
		const root = await mount({ qty: "Quantity must be positive" });

		const box = root.querySelector<HTMLElement>(".field-box")!;
		expect(box.hasAttribute("data-error")).toBe(true);
		expect(box.className).toContain("focus-within:ring-outline-red-3");
	});

	it("shows the message once and points the open control at it", async () => {
		const root = await mount({ qty: "Quantity must be positive" });

		root.querySelector<HTMLElement>('[data-fieldname="qty"]')!.click();
		await nextTick();

		const message = root.querySelector<HTMLElement>("span.text-sm[title]")!;
		expect(root.textContent!.split("Quantity must be positive")).toHaveLength(2);
		expect(message.id).not.toBe("");
		expect(root.querySelector("[data-control]")!.getAttribute("aria-describedby")).toBe(message.id);
	});

	it("gives no error id to a control that still draws its own error text", async () => {
		const root = await mount({ qty: "Quantity must be positive" }, "Select");

		root.querySelector<HTMLElement>('[data-fieldname="qty"]')!.click();
		await nextTick();

		expect(root.querySelector("[data-control]")!.getAttribute("aria-describedby")).toBeNull();
	});

	it("loses the red, the ring and the message on the next edit of the field", async () => {
		const errors = new FieldErrors();
		errors.mark("qty", "Quantity must be positive");
		const root = await mount(errors.drawn);
		expect(root.querySelector(".field-box")!.hasAttribute("data-error")).toBe(true);

		errors.clear("qty");
		await nextTick();

		expect(root.querySelector("span.text-sm[title]")).toBeNull();
		expect(root.querySelector(".field-box")!.hasAttribute("data-error")).toBe(false);
		expect(root.querySelector<HTMLElement>('[data-fieldname="qty"] span')!.className).not.toContain(
			"text-ink-red-6"
		);
	});

	it("loses every mark when a save starts", async () => {
		const errors = new FieldErrors();
		errors.mark("qty", "Quantity must be positive");
		const root = await mount(errors.drawn);

		errors.clearAll();
		await nextTick();

		expect(root.querySelector("span.text-sm[title]")).toBeNull();
	});
});
