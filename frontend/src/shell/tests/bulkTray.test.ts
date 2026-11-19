// The corner tray and the result panel: a run's progress, its outcome, View opens the panel,
// and the panel's tabs, Select failed, Retry failed and Open PDF.
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { createApp, h, nextTick, reactive, type App } from "vue";

const fake = vi.hoisted(() => ({ runs: [] as unknown[], dismiss: vi.fn(), listDocuments: vi.fn() }));

vi.mock("@framework/ui/api", async (importOriginal) => ({
	...(await importOriginal<typeof import("@framework/ui/api")>()),
	listDocuments: fake.listDocuments,
}));
vi.mock("../bulkRuns", async () => {
	const { computed } = await import("vue");
	return { useBulkRuns: () => computed(() => fake.runs), dismissBulkRun: fake.dismiss, followBulkRun: vi.fn() };
});

import BulkResultPanel from "../BulkResultPanel.vue";
import BulkTray from "../BulkTray.vue";
import { bulkPanel, bulkRunMeta, type BulkReport } from "../bulkOutcome";
import type { BulkRun } from "../bulkRuns";

let mounted: App | null = null;
const text = () => document.body.textContent ?? "";
const button = (label: string) =>
	[...document.body.querySelectorAll("button")].find((one) => one.textContent?.trim() === label);

async function settle() {
	await vi.advanceTimersByTimeAsync(50);
	await nextTick();
}

function run(extra: Partial<BulkRun> = {}): BulkRun {
	return {
		taskId: "T-1",
		taskName: "Bulk Delete",
		status: "Running",
		progress: 40,
		stage: "Deleting 2 of 5",
		result: null,
		error: null,
		...extra,
	};
}

async function mount(component: object, props: object = {}) {
	const host = document.createElement("div");
	document.body.append(host);
	mounted = createApp({ render: () => h(component, props) });
	mounted.mount(host);
	await settle();
}

beforeEach(() => {
	vi.useFakeTimers();
	vi.clearAllMocks();
	fake.runs = reactive([]);
	bulkPanel.value = null;
	bulkRunMeta.clear();
});

afterEach(() => {
	mounted?.unmount();
	mounted = null;
	document.body.innerHTML = "";
	vi.useRealTimers();
});

describe("BulkTray", () => {
	it("sits 16px in from the right, plus the navigation's width when it is on the right", async () => {
		fake.runs.push(run());
		await mount(BulkTray);
		expect(document.querySelector<HTMLElement>("[class*='bottom-[calc(6rem']")!.className).toContain(
			"right-[calc(1rem+var(--shell-nav-inset-right,0px))]"
		);
	});

	it("shows a live run with its stage, then its outcome", async () => {
		bulkRunMeta.set("T-1", { label: "Delete", doctype: "Lead" });
		fake.runs.push(run());
		await mount(BulkTray);
		expect(text()).toContain("Delete");
		expect(text()).toContain("Deleting 2 of 5");
		expect(button("View")).toBeUndefined();

		Object.assign(fake.runs[0] as BulkRun, {
			status: "Completed",
			result: { total: 5, done: ["A", "B", "C"], failed: [{ name: "D", error: "No" }, { name: "E", error: "No" }] },
		});
		await settle();
		expect(text()).toContain("3 done, 2 failed");
		expect(button("View")).toBeDefined();
	});

	it("opens the result panel from View", async () => {
		fake.runs.push(
			run({ status: "Completed", result: { total: 1, done: [], failed: [{ name: "D", error: "No" }] } })
		);
		await mount(BulkTray);
		button("View")!.click();
		await settle();
		expect(bulkPanel.value).toMatchObject({ total: 1, failed: [{ name: "D", error: "No" }] });
		expect(text()).toContain("D");
	});

	it("dismisses a clean run by itself after a few seconds, but keeps a run with failures", async () => {
		fake.runs.push(run({ status: "Completed", result: { total: 1, done: ["A"], failed: [] } }));
		await mount(BulkTray);
		expect(button("View")).toBeUndefined();
		await vi.advanceTimersByTimeAsync(6100);
		expect(fake.dismiss).toHaveBeenCalledWith("T-1");

		fake.dismiss.mockClear();
		fake.runs.splice(0, 1, run({ status: "Completed", result: { total: 1, done: [], failed: [{ name: "D", error: "No" }] } }));
		await settle();
		await vi.advanceTimersByTimeAsync(6100);
		expect(fake.dismiss).not.toHaveBeenCalled();
	});

	it("keeps a run that ended without a result", async () => {
		fake.runs.push(run({ status: "Failed", error: "Worker lost" }));
		await mount(BulkTray);
		await vi.advanceTimersByTimeAsync(6100);
		expect(fake.dismiss).not.toHaveBeenCalled();
	});

	it("offers a print run's PDF", async () => {
		fake.runs.push(run({ status: "Completed", result: { total: 1, done: ["A"], failed: [], file_url: "/files/p.pdf" } }));
		await mount(BulkTray);
		expect(button("View")).toBeDefined();
	});
});

describe("BulkResultPanel", () => {
	const report = (extra: Partial<BulkReport> = {}): BulkReport => ({
		label: "Submit",
		doctype: "Leave",
		total: 4,
		done: [{ name: "A" }],
		failed: [
			{ name: "B", error: "Not saved" },
			{ name: "C", error: "" },
		],
		queued: [{ name: "D" }],
		...extra,
	});

	it("lists the failures first with one reason each, and a placeholder for a blank reason", async () => {
		await mount(BulkResultPanel, { report: report() });
		expect(text()).toContain("Submit · 4 records");
		expect(text()).toContain("B");
		expect(text()).toContain("Not saved");
		expect(text()).toContain("No reason was given.");
		expect(text()).not.toContain("In the Submission Queue");
	});

	it("switches tabs to the queued and done records", async () => {
		await mount(BulkResultPanel, { report: report() });
		button("Queued 1")!.click();
		await settle();
		expect(text()).toContain("In the Submission Queue");
		button("Done 1")!.click();
		await settle();
		expect(text()).not.toContain("In the Submission Queue");
	});

	it("selects the failed names and closes", async () => {
		const select = vi.fn();
		const close = vi.fn();
		await mount(BulkResultPanel, { report: report({ select }), onClose: close });
		button("Select failed")!.click();
		await settle();
		expect(select).toHaveBeenCalledWith(["B", "C"]);
		expect(close).toHaveBeenCalled();
	});

	it("retries the failed names", async () => {
		const retry = vi.fn().mockResolvedValue(undefined);
		await mount(BulkResultPanel, { report: report({ retry }) });
		button("Retry failed")!.click();
		await settle();
		expect(retry).toHaveBeenCalledWith(["B", "C"]);
	});

	it("links the merged PDF of a print run", async () => {
		await mount(BulkResultPanel, { report: report({ fileUrl: "/files/p.pdf" }) });
		expect(document.body.querySelector("a[href='/files/p.pdf']")).not.toBeNull();
	});

	it("moves a queued record to Done while it is open", async () => {
		fake.listDocuments.mockResolvedValue({ data: [{ ref_docname: "D", status: "Finished" }] });
		const open = report({ failed: [] });
		bulkPanel.value = open;
		await mount(BulkResultPanel, { report: open });
		await vi.advanceTimersByTimeAsync(3100);
		expect(bulkPanel.value?.done.map(({ name }) => name)).toEqual(["A", "D"]);
		expect(bulkPanel.value?.queued).toEqual([]);
	});
});
