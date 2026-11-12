import { afterEach, describe, expect, it, vi } from "vitest";
import { createApp, h, nextTick, ref, type App } from "vue";
import type { DeleteOutcome } from "@/list/useListView";
import DeleteDialog from "../DeleteDialog.vue";

const fake = vi.hoisted(() => ({ success: vi.fn(), info: vi.fn() }));

vi.mock("frappe-ui", async (importOriginal) => ({
	...(await importOriginal<typeof import("frappe-ui")>()),
	toast: { success: fake.success, info: fake.info },
}));

let mounted: App | null = null;

async function settle() {
	for (let turn = 0; turn < 6; turn++) await nextTick();
	await new Promise((resolve) => setTimeout(resolve));
	await nextTick();
}

async function open(run: () => Promise<DeleteOutcome>, mountedOpen = false, scope = {}) {
	const host = document.createElement("div");
	document.body.append(host);
	const shown = ref(mountedOpen);
	mounted = createApp({ render: () => h(DeleteDialog, { modelValue: shown.value, count: 2, ...scope, run }) });
	mounted.mount(host);
	if (!mountedOpen) shown.value = true;
	await settle();
}

async function confirm() {
	const button = Array.from(document.body.querySelectorAll("button")).find((b) => b.textContent?.trim() === "Delete");
	button!.click();
	await settle();
}

const text = () => document.body.textContent ?? "";

afterEach(() => {
	mounted?.unmount();
	mounted = null;
	document.body.innerHTML = "";
	vi.clearAllMocks();
});

describe("DeleteDialog", () => {
	it("warns that a delete cannot be undone", async () => {
		await open(async () => ({ deleted: [], failed: [] }));
		expect(text()).toContain("Delete 2 selected records?");
		expect(text()).toContain("This cannot be undone.");
	});

	it("names the scope when the run takes every record the filters show", async () => {
		await open(async () => ({ deleted: [], failed: [] }), false, { all: true, count: 1240 });
		expect(text()).toContain("Delete all 1,240 matching records?");
		mounted?.unmount();
		await open(async () => ({ deleted: [], failed: [] }), false, { all: true, count: 10000, approx: true });
		expect(text()).toContain("Delete all 10,000+ matching records?");
	});

	it("counts the rows when it mounts already open, as the lazy list chunk does", async () => {
		await open(async () => ({ deleted: [], failed: [] }), true);
		expect(text()).toContain("Delete 2 selected records?");
	});

	it("keeps the dialog open with each failure, one per line", async () => {
		await open(async () => ({ deleted: ["A"], failed: [{ name: "B", error: "linked" }] }));
		await confirm();
		expect(fake.success).toHaveBeenCalledWith("Deleted 1 record");
		expect(text()).toContain("B: linked");
	});

	it("shows why the whole run was refused", async () => {
		await open(async () => Promise.reject(new Error("Bulk actions are off for you")));
		await confirm();
		expect(text()).toContain("Bulk actions are off for you");
		expect(fake.success).not.toHaveBeenCalled();
	});

	it("closes without a toast when the shell reports the run", async () => {
		await open(async () => ({ deleted: [], failed: [] }));
		await confirm();
		expect(fake.success).not.toHaveBeenCalled();
		expect(text()).not.toContain("This cannot be undone.");
	});
});
