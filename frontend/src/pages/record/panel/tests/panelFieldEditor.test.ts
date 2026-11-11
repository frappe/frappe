// An open panel row shows the field's own placeholder, else `Add <Label>...`; a Password row masks its value one dot per character.
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
	setup: (props) => () => h("input", { placeholder: props.field?.placeholder }),
});

const mounted: ReturnType<typeof createApp>[] = [];

afterEach(() => {
	for (const app of mounted.splice(0)) app.unmount();
	document.body.innerHTML = "";
});

function mount(field: FieldNode, doc: Record<string, any>) {
	const root = document.createElement("div");
	document.body.appendChild(root);
	const app = createApp(defineComponent({ render: () => h(PanelField, { field }) }));
	app.provide(DocKey, ref(doc));
	app.provide(UpdateKey, vi.fn());
	app.provide(CommitKey, NO_COMMIT);
	app.provide(ResolveFieldKey, () => Control);
	app.mount(root);
	mounted.push(app);
	return root;
}

async function openEditor(field: FieldNode) {
	const root = mount(field, {});
	root.querySelector<HTMLElement>(`[data-fieldname="${field.fieldname}"]`)!.click();
	await nextTick();
	return root.querySelector("input")!;
}

describe("a panel row's editor placeholder", () => {
	it("is the field's own placeholder when its meta sets one", async () => {
		const input = await openEditor({
			fieldname: "nick",
			fieldtype: "Data",
			label: "Nickname",
			placeholder: "Enter a nickname",
		});

		expect(input.placeholder).toBe("Enter a nickname");
	});

	it("is `Add <Label>...` when the meta sets none", async () => {
		const input = await openEditor({ fieldname: "nick", fieldtype: "Data", label: "Nickname" });

		expect(input.placeholder).toBe("Add Nickname...");
	});
});

describe("a Password row at rest", () => {
	const password: FieldNode = { fieldname: "pw", fieldtype: "Password", label: "Password" };

	it("draws one dot per character, without the value in the page of the value, as the open input does", () => {
		const root = mount(password, { pw: "secret" });
		const secret = root.querySelector<HTMLElement>("[data-fieldname] span.truncate")!;

		expect(secret.textContent).toBe("••••••");
		expect(root.textContent).not.toContain("secret");
		expect(secret.className).toContain("-webkit-text-security:disc");
	});

	it("shows the row's placeholder for an empty value", () => {
		const root = mount(password, {});

		expect(root.querySelector("[data-fieldname] span.truncate")!.textContent).toBe("Add Password...");
	});
});
