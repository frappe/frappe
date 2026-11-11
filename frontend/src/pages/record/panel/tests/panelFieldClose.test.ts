// An open panel row closes on a press outside it (keeping the draft), but not on a press in its cell or a popover.
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

import { CommitKey, DocKey, NO_COMMIT, ResolveFieldKey, UpdateKey } from "@framework/ui/FormLayout/types";
import type { FieldNode } from "@framework/ui/FormLayout/types";
import PanelField from "../PanelField.vue";

const Control = defineComponent({
	props: { panel: Boolean, field: Object },
	setup: (props) => () =>
		h("input", { "data-control": "", "data-panel": props.panel, placeholder: props.field?.placeholder }),
});

const mounted: ReturnType<typeof createApp>[] = [];

afterEach(() => {
	for (const app of mounted.splice(0)) app.unmount();
	document.body.innerHTML = "";
});

const qty: FieldNode = { fieldname: "qty", fieldtype: "Int", label: "Qty" };

async function open() {
	const root = document.createElement("div");
	document.body.appendChild(root);
	const app = createApp(defineComponent({ render: () => h(PanelField, { field: qty }) }));
	app.provide(DocKey, ref({ qty: 2 }));
	app.provide(UpdateKey, vi.fn());
	app.provide(CommitKey, NO_COMMIT);
	app.provide(ResolveFieldKey, () => Control);
	app.mount(root);
	mounted.push(app);
	root.querySelector<HTMLElement>('[data-fieldname="qty"]')!.click();
	await nextTick();
	return root;
}

const press = (target: Element) =>
	target.dispatchEvent(new PointerEvent("pointerdown", { bubbles: true }));

describe("an open panel row", () => {
	it("draws its control in panel mode with the row's one placeholder", async () => {
		const root = await open();
		const control = root.querySelector("[data-control]")!;

		expect(control.getAttribute("data-panel")).toBe("true");
		expect(control.getAttribute("placeholder")).toBe("Add Qty...");
	});

	it("closes on a press on a blank part of the page", async () => {
		const root = await open();

		press(document.body);
		await nextTick();

		expect(root.querySelector("[data-control]")).toBeNull();
	});

	it("stays open on a press in its cell or in a popover", async () => {
		const root = await open();
		const popover = document.body.appendChild(document.createElement("div"));
		popover.setAttribute("data-reka-popper-content-wrapper", "");

		press(root.querySelector("[data-control]")!);
		press(popover);
		await nextTick();

		expect(root.querySelector("[data-control]")).not.toBeNull();
	});

	it("closes on a press on another row", async () => {
		const root = await open();
		const other = document.body.appendChild(document.createElement("button"));

		press(other);
		await nextTick();

		expect(root.querySelector("[data-control]")).toBeNull();
	});
});
