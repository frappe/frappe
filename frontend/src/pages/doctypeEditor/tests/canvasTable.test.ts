// A Table field on the canvas whose child meta is loading or failed says so, not "No columns to display".
import { afterEach, expect, it, vi } from "vitest";
import { computed, createApp, h, ref } from "vue";
import type { RawMetaField } from "@framework/ui/FormLayout/types";
import CanvasTable from "../CanvasTable.vue";

const meta = ref<{ fields: RawMetaField[] } | null>(null);
const error = ref<unknown>(null);
const reload = vi.fn();

vi.mock("@framework/ui/useDoctypeMeta", () => ({
	useDoctypeMeta: () => ({ meta: computed(() => meta.value), error: computed(() => error.value), reload }),
}));
vi.mock("@framework/ui/FormLayout", () => ({
	FormLayoutField: { render: () => h("div", { "data-grid": "" }, "Grid") },
	mapField: (field: RawMetaField) => field,
}));

const items = { fieldname: "items", label: "Items", fieldtype: "Table", options: "Invoice Item", reqd: 1 } as RawMetaField;

let app: ReturnType<typeof createApp> | null = null;

afterEach(() => {
	app?.unmount();
	app = null;
	document.body.innerHTML = "";
	meta.value = null;
	error.value = null;
	reload.mockClear();
});

function mount() {
	const root = document.createElement("div");
	document.body.appendChild(root);
	app = createApp({ render: () => h(CanvasTable, { field: items }) });
	app.mount(root);
	return root;
}

it("shows a skeleton under the label while the child's meta is loading", () => {
	const root = mount();
	expect(root.querySelector("[data-child-columns='loading']")?.textContent).toContain("Items");
	expect(root.querySelector("[data-grid]")).toBeNull();
});

it("shows the failure and a Try again that reloads the meta", () => {
	error.value = new Error("Network down");
	const root = mount();
	const failed = root.querySelector("[data-child-columns='failed']")!;
	expect(failed.textContent).toContain("Could not load the columns of Invoice Item.");
	expect(failed.closest("[inert]")).toBeNull();
	failed.querySelector("button")!.click();
	expect(reload).toHaveBeenCalledOnce();
	expect(root.querySelector("[data-grid]")).toBeNull();
});

it("draws the grid once the meta has its fields, empty ones included", () => {
	meta.value = { fields: [] };
	const root = mount();
	expect(root.querySelector("[inert] [data-grid]")).not.toBeNull();
	expect(root.querySelector("[data-child-columns]")).toBeNull();
});
