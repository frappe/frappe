// A panel row for a phone value draws the field actions the host hands it, and their click never opens the editor.
import { afterEach, describe, expect, it, vi } from "vitest";
import { createApp, defineComponent, h, nextTick, ref } from "vue";

vi.mock("frappe-ui", async (importOriginal) => ({
	...((await importOriginal()) as Record<string, unknown>),
	call: vi.fn(),
	toast: { success: vi.fn(), error: vi.fn() },
	createResource: () => ({
		data: null,
		loading: false,
		fetch() {},
		reload() {},
	}),
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
import { FieldActionsKey } from "@framework/ui/fields/types";
import type { FieldAction } from "@framework/ui/fields/types";
import PanelField from "../PanelField.vue";
import { PanelContextKey } from "../context";

const Control = defineComponent({
	render: () => h("input", { "data-control": "" }),
});

const mounted: ReturnType<typeof createApp>[] = [];

afterEach(() => {
	for (const app of mounted.splice(0)) app.unmount();
	document.body.innerHTML = "";
});

function action(label: string, run = vi.fn()): FieldAction {
	return { act: `shell.crm.${label}`, label, icon: "lucide-phone", run };
}

async function mount(
	field: Partial<FieldNode>,
	value: string,
	actions: FieldAction[] | null,
	forRecord?: (record: unknown) => void
) {
	const node = {
		fieldname: "mobile_no",
		label: "Mobile",
		...field,
	} as FieldNode;
	const root = document.createElement("div");
	document.body.appendChild(root);
	const app = createApp(defineComponent({ render: () => h(PanelField, { field: node }) }));
	app.provide(DocKey, ref({ mobile_no: value }));
	app.provide(UpdateKey, vi.fn());
	app.provide(CommitKey, NO_COMMIT);
	app.provide(ResolveFieldKey, () => Control);
	app.provide(PanelContextKey, { doctype: "Lead", docname: "L1" } as never);
	if (actions)
		app.provide(FieldActionsKey, {
			for: (_field, current, record) => {
				forRecord?.(record);
				return current ? actions : [];
			},
		});
	app.mount(root);
	mounted.push(app);
	await nextTick();
	return root;
}

const phone = { fieldtype: "Phone" };
const dataPhone = { fieldtype: "Data", options: "Phone" };

describe("field actions on a panel row", () => {
	it.each([phone, dataPhone])("draws one action as an icon button for %o", async (field) => {
		const run = vi.fn();
		const root = await mount(field, "123", [action("Call", run)]);
		const button = root.querySelector<HTMLButtonElement>("[data-slot='field-action']")!;
		expect(button.getAttribute("aria-label")).toBe("Call");
		button.click();
		await nextTick();
		expect(run).toHaveBeenCalledOnce();
		expect(root.querySelector("[data-control]")).toBeNull();
	});

	it("draws two or more actions as a menu that does not open the editor", async () => {
		const root = await mount(phone, "123", [action("Call"), action("Text")]);
		expect(root.querySelector("[data-slot='field-action']")).toBeNull();
		const trigger = root.querySelector<HTMLButtonElement>("[data-slot='field-actions']")!;
		trigger.click();
		await nextTick();
		expect(root.querySelector("[data-control]")).toBeNull();
	});

	it("draws an Email field's action and names the record it sits on", async () => {
		let named: unknown;
		const root = await mount(
			{ fieldtype: "Data", options: "Email" },
			"a@x.com",
			[action("Email")],
			(record) => (named = record)
		);
		expect(root.querySelector("[data-slot='field-action']")?.getAttribute("aria-label")).toBe("Email");
		expect(named).toEqual({ doctype: "Lead", name: "L1", surface: "record" });
	});

	it("draws nothing for an empty value", async () => {
		const root = await mount(phone, "", [action("Call")]);
		expect(root.querySelector("button")).toBeNull();
	});

	it("draws nothing without a host", async () => {
		const root = await mount(phone, "123", null);
		expect(root.querySelector("button")).toBeNull();
	});

	it("draws the action on a read-only row", async () => {
		const root = await mount({ ...phone, readOnly: true }, "123", [action("Call")]);
		expect(root.querySelector("[data-slot='field-action']")).not.toBeNull();
	});

	it("draws none on another Data option", async () => {
		const root = await mount({ fieldtype: "Data", options: "URL" }, "a@x.com", [action("Call")]);
		expect(root.querySelector("[data-slot='field-action']")).toBeNull();
	});

	it("still opens the editor from the row's text", async () => {
		const root = await mount(phone, "123", [action("Call")]);
		root.querySelector<HTMLElement>("[data-fieldname='mobile_no']")!.click();
		await nextTick();
		expect(root.querySelector("[data-control]")).not.toBeNull();
	});
});
