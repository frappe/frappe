// A marked panel row: the value in red, the message on two lines at most under its box, the red
// focus ring, and the control the row opens pointing at the message.
import { afterEach, describe, expect, it, vi } from "vitest";
import { createApp, defineComponent, h, isRef, nextTick, ref } from "vue";
import type { Ref } from "vue";

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

async function mount(
	errors: Record<string, string> | Ref<Record<string, any>>,
	fieldtype = "Int",
	record: Record<string, any> = {}
) {
	const root = document.createElement("div");
	document.body.appendChild(root);
	const app = createApp(defineComponent({ render: () => h(PanelField, { field: { ...qty, fieldtype } }) }));
	app.provide(DocKey, ref({ qty: -2, ...record }));
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

	it("insets the message to the value's x", async () => {
		const root = await mount({ qty: "Quantity must be positive" });
		const row = root.querySelector<HTMLElement>('[data-fieldname="qty"]')!;
		const message = root.querySelector<HTMLElement>("span.text-sm[title]")!;

		expect(row.className).toContain("px-2");
		expect(message.className).toContain("px-2");
	});

	it("drops a leading name of this record from the row's message and from what the control points at", async () => {
		const stored = ref<Record<string, any>>({ qty: "Task TASK-1: 'Qty' (-2) is too small" });
		const root = await mount(stored, "Int", { doctype: "Task", name: "TASK-1" });

		const message = root.querySelector<HTMLElement>("span.text-sm[title]")!;
		expect(message.textContent!.trim()).toBe("'Qty' (-2) is too small");
		expect(message.title).toBe("'Qty' (-2) is too small");
		expect(stored.value.qty).toBe("Task TASK-1: 'Qty' (-2) is too small");

		root.querySelector<HTMLElement>('[data-fieldname="qty"]')!.click();
		await nextTick();
		const described = root.querySelector("[data-control]")!.getAttribute("aria-describedby");
		expect(root.querySelector(`[id="${described}"]`)!.textContent!.trim()).toBe(
			"'Qty' (-2) is too small"
		);
	});

	it("drops the prefix from every message of a row", async () => {
		const root = await mount(
			{ qty: ["Task TASK-1: first", "Task TASK-1: second"] as any },
			"Int",
			{ doctype: "Task", name: "TASK-1" }
		);

		expect(root.querySelector("span.text-sm[title]")!.textContent!.trim()).toBe("first second");
	});

	it("keeps a message that names another record", async () => {
		const root = await mount({ qty: "Task TASK-2: 'Qty' (-2) is too small" }, "Int", {
			doctype: "Task",
			name: "TASK-1",
		});

		expect(root.querySelector("span.text-sm[title]")!.textContent!.trim()).toBe(
			"Task TASK-2: 'Qty' (-2) is too small"
		);
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
		const root = await mount({ qty: "Quantity must be positive" }, "Barcode");

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
