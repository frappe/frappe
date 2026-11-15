// The Preview tab's layout and record reads: a skeleton while they load, the error and Try again when they fail.
import { afterEach, expect, it, vi } from "vitest";
import { computed, createApp, h, ref } from "vue";
import PreviewTab from "../PreviewTab.vue";

const { getDocument } = vi.hoisted(() => ({ getDocument: vi.fn() }));
vi.mock("@framework/ui/api", async (original) => ({
	...(await original<typeof import("@framework/ui/api")>()),
	getDocument,
}));

const layoutLoading = ref(false);
const layoutError = ref<unknown>(null);
const reloadLayout = vi.fn();
vi.mock("@/recordPage/formLayoutSource/useFormLayout", () => ({
	useFormLayout: () => ({
		layout: computed(() => ({ tabs: [] })),
		loading: computed(() => layoutLoading.value),
		error: computed(() => layoutError.value),
		reload: reloadLayout,
	}),
}));
vi.mock("@framework/ui/FormLayout", () => ({
	FormLayout: { render: () => h("div", { "data-form": "" }) },
}));

let app: ReturnType<typeof createApp> | null = null;
const picks: (string | null)[] = [];

afterEach(() => {
	app?.unmount();
	app = null;
	document.body.innerHTML = "";
	layoutLoading.value = false;
	layoutError.value = null;
	reloadLayout.mockReset();
	getDocument.mockReset();
	picks.length = 0;
});

function mount(record: string | null) {
	const root = document.createElement("div");
	document.body.appendChild(root);
	app = createApp({
		render: () =>
			h(PreviewTab, {
				doctype: "Task Note",
				record,
				latest: ["TN-1"],
				titleField: "",
				onPick: (name: string | null) => picks.push(name),
			}),
	});
	app.mount(root);
	return root;
}

const failure = (root: Element) => root.querySelector("[data-preview-failure]");

it("shows a skeleton, not a blank pane, while the layout loads", () => {
	layoutLoading.value = true;
	const root = mount(null);
	expect(root.querySelector("[data-form-skeleton]")).not.toBeNull();
	expect(root.querySelector("[data-form]")).toBeNull();
});

it("shows the layout's error with a Try again that reloads it", () => {
	layoutError.value = new Error("Layout read failed");
	const root = mount(null);
	expect(failure(root)!.textContent).toContain("Could not load the layout. Layout read failed");
	failure(root)!.querySelector("button")!.click();
	expect(reloadLayout).toHaveBeenCalledOnce();
});

it("shows a failed record read and keeps the picked record", async () => {
	getDocument.mockRejectedValue(new Error("Gone away"));
	const root = mount("TN-1");
	await vi.waitFor(() => expect(failure(root)).not.toBeNull());
	expect(failure(root)!.textContent).toContain("Could not load TN-1. Gone away");
	expect(picks).toEqual([]);
	expect(root.querySelector("[data-preview-record]")!.textContent).toContain("TN-1");
});

it("reads the record again on Try again", async () => {
	getDocument.mockRejectedValueOnce(new Error("Gone away"));
	getDocument.mockResolvedValueOnce({ data: { name: "TN-1" } });
	const root = mount("TN-1");
	await vi.waitFor(() => expect(failure(root)).not.toBeNull());
	failure(root)!.querySelector("button")!.click();
	await vi.waitFor(() => expect(failure(root)).toBeNull());
	expect(root.querySelector("[data-form]")).not.toBeNull();
});
