// The Rename dialog: the name box starts with the old name, and the lines count what a rename moves.
import { afterEach, expect, it, vi } from "vitest";
import { createApp, h, nextTick, type App } from "vue";

const { runMethod } = vi.hoisted(() => ({ runMethod: vi.fn() }));
vi.mock("@framework/ui/api", () => ({ runMethod }));
vi.mock("frappe-ui", async () => {
	const { defineComponent, h } = await import("vue");
	const stub = (tag: string) => defineComponent({ inheritAttrs: true, setup: (_p, { slots }) => () => h(tag, slots.default?.()) });
	return {
		Button: defineComponent({ props: ["label", "disabled"], setup: (p) => () => h("button", { disabled: p.disabled }, p.label) }),
		TextInput: defineComponent({
			props: ["modelValue"],
			setup: (p, { expose }) => {
				expose({ focus: () => {} });
				return () => h("input", { value: p.modelValue });
			},
		}),
		Tooltip: stub("span"),
	};
});

import RenameDoctypeDialog from "../RenameDoctypeDialog.vue";

const apps: App[] = [];
afterEach(() => apps.splice(0).forEach((app) => app.unmount()));

async function open(records: number | null, links: number) {
	runMethod.mockResolvedValue({ data: links });
	const root = document.createElement("div");
	const app = createApp({ render: () => h(RenameDoctypeDialog, { doctype: "Store", records, close: () => {} }) });
	app.mount(root);
	apps.push(app);
	await nextTick();
	await nextTick();
	return root;
}

it("starts with the old name, and counts the records and the fields that point to it", async () => {
	const root = await open(1200, 3);
	expect(root.querySelector("input")!.value).toBe("Store");
	expect(runMethod).toHaveBeenCalledWith("frappe.desk.doctype_editor.danger.rename_effects", { doctype: "Store" }, { http: "GET" });
	const lines = [...root.querySelectorAll("li")].map((li) => li.textContent?.trim());
	expect(lines).toEqual([
		"The table tabStore becomes tabStore, with its 1,200 records.",
		"3 Link and Table fields in other DocTypes point to Store.",
	]);
	expect(root.querySelector("button[type=submit], button:last-child")!.hasAttribute("disabled")).toBe(true);
});

it("leaves out the record count while it is unknown", async () => {
	const root = await open(null, 1);
	expect(root.querySelector("li")!.textContent?.trim()).toBe("The table tabStore becomes tabStore.");
});
