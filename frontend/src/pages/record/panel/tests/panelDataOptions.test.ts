// A panel row leads to where a Data value points, and an editable row still opens its editor.
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

async function mount(options: string, value: string, readOnly = false) {
	const field: FieldNode = { fieldname: "f", fieldtype: "Data", label: "F", options, readOnly };
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

describe("a panel row for a Data option", () => {
	it("draws a read-only Email as a mailto link", async () => {
		const root = await mount("Email", "a@x.com, b@y.com", true);
		const link = root.querySelector<HTMLAnchorElement>("[data-slot='mail-link']");
		expect(link?.getAttribute("href")).toBe("mailto:a@x.com,b@y.com");
		expect(link?.textContent).toBe("a@x.com, b@y.com");
	});

	it("opens an editable Email's editor from its text, with the mail link on the arrow", async () => {
		const root = await mount("Email", "a@x.com");
		expect(root.querySelector("[data-slot='mail-link']")).toBeNull();
		const arrow = root.querySelector<HTMLAnchorElement>("[data-slot='mail-arrow']");
		expect(arrow?.getAttribute("href")).toBe("mailto:a@x.com");
		expect(arrow?.target).toBe("");
		root.querySelector<HTMLElement>("[data-fieldname='f']")!.click();
		await nextTick();
		expect(root.querySelector("[data-control]")).not.toBeNull();
	});

	it("does not open the editor when the arrow is clicked", async () => {
		const root = await mount("URL", "https://x.com");
		const arrow = root.querySelector<HTMLAnchorElement>("[data-slot='open-url']")!;
		arrow.addEventListener("click", (event) => event.preventDefault());
		arrow.click();
		await nextTick();
		expect(root.querySelector("[data-control]")).toBeNull();
	});

	it.each([
		["https://x.com", false, "https://x.com/"],
		["https://x.com", true, "https://x.com/"],
		["javascript:alert(1)", false, null],
		["ftp://x", true, null],
	])("draws the URL arrow for %s (read-only %s): %s", async (value, readOnly, href) => {
		const root = await mount("URL", value, readOnly);
		const arrow = root.querySelector<HTMLAnchorElement>("[data-slot='open-url']");
		expect(arrow?.getAttribute("href") ?? null).toBe(href);
		if (arrow) expect(arrow.target).toBe("_blank");
	});

	it.each(["Phone", "Name", "Barcode"])("draws %s as plain text", async (options) => {
		const root = await mount(options, "a@x.com", true);
		expect(root.querySelector("a")).toBeNull();
	});

	it("shows an IBAN in groups of four", async () => {
		const root = await mount("IBAN", "DE89370400440532013000");
		expect(root.textContent).toContain("DE89 3704 0044 0532 0130 00");
	});
});
