// A Link or Dynamic Link row in the side panel, at rest: an arrow to the record, apart from the editor.
import { afterEach, describe, expect, it } from "vitest";
import { createApp, defineComponent, h, nextTick, ref } from "vue";
import type { App } from "vue";
import {
	DocKey,
	LinkTitlesKey,
	NO_COMMIT,
	CommitKey,
	ResolveFieldKey,
	UpdateKey,
} from "@framework/ui/components/FormLayout/types";
import type { FieldNode } from "@framework/ui/components/FormLayout/types";
import { RecordLinkKey } from "@framework/ui/components/Fields/types";
import PanelField from "../PanelField.vue";

const Editor = defineComponent({ setup: () => () => h("input", { "data-editor": "" }) });

let app: App | undefined;
let opened: [string, string][];

afterEach(() => {
	app?.unmount();
	document.body.innerHTML = "";
});

function render(field: FieldNode, doc: Record<string, any>) {
	opened = [];
	const root = document.createElement("div");
	document.body.appendChild(root);
	app = createApp({ render: () => h(PanelField, { field }) });
	app.provide(DocKey, ref(doc));
	app.provide(UpdateKey, () => {});
	app.provide(CommitKey, NO_COMMIT);
	app.provide(ResolveFieldKey, () => Editor);
	app.provide(LinkTitlesKey, ref({ "Customer::CUST-001": "Acme Corp" }));
	app.provide(RecordLinkKey, {
		href: (doctype, name) => `/desk/${doctype.toLowerCase()}/${name}`,
		open: (doctype, name) => opened.push([doctype, name]),
	});
	app.mount(root);
	return root;
}

const customer: FieldNode = { fieldname: "customer", fieldtype: "Link", label: "Customer", options: "Customer" };

describe("a Link row in the panel", () => {
	it("links to the record, labelled with its title", () => {
		const root = render(customer, { customer: "CUST-001" });
		const arrow = root.querySelector("a")!;

		expect(arrow.getAttribute("href")).toBe("/desk/customer/CUST-001");
		expect(arrow.getAttribute("aria-label")).toBe("Open Acme Corp");
	});

	it("opens the record on the arrow, not the editor", async () => {
		const root = render(customer, { customer: "CUST-001" });

		root.querySelector("a")!.dispatchEvent(new MouseEvent("click", { bubbles: true, cancelable: true }));
		await nextTick();

		expect(opened).toEqual([["Customer", "CUST-001"]]);
		expect(root.querySelector("[data-editor]")).toBeNull();
	});

	it("opens the editor on the text", async () => {
		const root = render(customer, { customer: "CUST-001" });

		root.querySelector<HTMLElement>("[data-fieldname] span")!.click();
		await nextTick();

		expect(root.querySelector("[data-editor]")).not.toBeNull();
		expect(opened).toEqual([]);
	});

	it("has no arrow with no value", () => {
		const root = render(customer, { customer: null });

		expect(root.querySelector("a")).toBeNull();
	});

	it("links a Dynamic Link to the record in its sibling field's doctype", () => {
		const reference: FieldNode = {
			fieldname: "reference_name",
			fieldtype: "Dynamic Link",
			label: "Reference",
			options: "reference_doctype",
		};
		const root = render(reference, { reference_doctype: "Invoice", reference_name: "SI-001" });

		expect(root.querySelector("a")?.getAttribute("href")).toBe("/desk/invoice/SI-001");
	});
});
