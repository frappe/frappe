// What a bulk act's reply becomes: the tray for a background run, a toast for a clean inline run,
// the result panel on any failure; Retry failed re-sends to the failed names; queued records settle.
import { beforeEach, describe, expect, it, vi } from "vitest";

const fake = vi.hoisted(() => ({
	listDocuments: vi.fn(),
	follow: vi.fn(),
	toast: { success: vi.fn(), info: vi.fn() },
}));

vi.mock("@framework/ui/api", () => ({ listDocuments: fake.listDocuments }));
vi.mock("frappe-ui", () => ({ toast: fake.toast }));
vi.mock("../bulkRuns", () => ({ followBulkRun: fake.follow }));

import { bulkPanel, bulkRunMeta, reportOfRun, runBulk, settleQueued, type BulkReport } from "../bulkOutcome";
import { bulkTrayShown } from "../bulkTrayFlag";

const send = vi.fn();
const finished = vi.fn();
const select = vi.fn();
const options = { label: "Submit", doctype: "Leave", send, select, finished };

beforeEach(() => {
	vi.clearAllMocks();
	bulkPanel.value = null;
	bulkRunMeta.clear();
	bulkTrayShown.value = false;
});

describe("runBulk", () => {
	it("follows a background run in the tray and keeps its retry and select", async () => {
		send.mockResolvedValue({ data: { task_id: "T-1", job_id: "J-1" } });
		await runBulk(options);
		expect(bulkTrayShown.value).toBe(true);
		expect(fake.follow).toHaveBeenCalledWith("T-1", expect.any(Function));
		expect(bulkRunMeta.get("T-1")).toMatchObject({ label: "Submit", doctype: "Leave", select });
		expect(fake.toast.info).toHaveBeenCalledWith("Submit is running in the background");
		expect(bulkPanel.value).toBeNull();
		fake.follow.mock.calls[0][1]();
		expect(finished).toHaveBeenCalled();
	});

	it("toasts an inline run that passed in full and reloads", async () => {
		send.mockResolvedValue({ data: { total: 2, done: ["A", "B"], failed: [] } });
		await runBulk(options);
		expect(fake.toast.success).toHaveBeenCalledWith("2 records done");
		expect(finished).toHaveBeenCalled();
		expect(bulkPanel.value).toBeNull();
	});

	it("opens the result panel on any failure", async () => {
		send.mockResolvedValue({ data: { total: 2, done: ["A"], failed: [{ name: "B", error: "Not saved" }] } });
		await runBulk(options);
		expect(bulkPanel.value).toMatchObject({ label: "Submit", total: 2, failed: [{ name: "B", error: "Not saved" }] });
		expect(fake.toast.success).not.toHaveBeenCalled();
	});

	it("retries the failed names only, through the same send", async () => {
		send.mockResolvedValueOnce({ data: { total: 2, done: ["A"], failed: [{ name: "B", error: "x" }] } });
		await runBulk(options);
		send.mockResolvedValueOnce({ data: { total: 1, done: ["B"], failed: [] } });
		await bulkPanel.value!.retry!(["B"]);
		expect(send).toHaveBeenLastCalledWith(["B"]);
		expect(fake.toast.success).toHaveBeenCalledWith("1 record done");
	});
});

describe("reportOfRun", () => {
	it("builds the panel's report from a settled run with the retry it started with", () => {
		const retry = vi.fn();
		bulkRunMeta.set("T-1", { label: "Delete", doctype: "Lead", retry, select });
		const report = reportOfRun("T-1", "fallback", {
			total: 3,
			done: ["A"],
			failed: [{ name: "B", error: "" }],
			queued: [{ name: "C", doctype: "Lead" }],
			file_url: "/files/x.pdf",
		});
		expect(report).toMatchObject({
			label: "Delete",
			doctype: "Lead",
			done: [{ name: "A" }],
			failed: [{ name: "B", error: "" }],
			queued: [{ name: "C", doctype: "Lead" }],
			fileUrl: "/files/x.pdf",
			retry,
			select,
		});
	});
});

describe("settleQueued", () => {
	const report = (): BulkReport => ({
		label: "Submit",
		doctype: "Leave",
		total: 3,
		done: [],
		failed: [],
		queued: [{ name: "A" }, { name: "B" }, { name: "C" }],
	});

	it("moves queued records the Submission Queue finished into done or failed", async () => {
		fake.listDocuments.mockResolvedValue({
			data: [
				{ ref_docname: "A", status: "Finished" },
				{ ref_docname: "B", status: "Failed", exception: "Traceback\nValidationError: Bad" },
				{ ref_docname: "C", status: "Queued" },
			],
		});
		const more = await settleQueued(report());
		expect(more).toBe(true);
		expect(bulkPanel.value).toMatchObject({
			done: [{ name: "A" }],
			failed: [{ name: "B", error: "ValidationError: Bad" }],
			queued: [{ name: "C" }],
		});
		expect(fake.listDocuments.mock.calls[0][1].filters).toEqual({
			ref_doctype: "Leave",
			ref_docname: ["in", ["A", "B", "C"]],
		});
	});

	it("stops asking once nothing is queued", async () => {
		fake.listDocuments.mockResolvedValue({ data: [{ ref_docname: "A", status: "Finished" }] });
		expect(await settleQueued({ ...report(), queued: [{ name: "A" }] })).toBe(false);
		expect(await settleQueued({ ...report(), queued: [] })).toBe(false);
		expect(fake.listDocuments).toHaveBeenCalledTimes(1);
	});
});
