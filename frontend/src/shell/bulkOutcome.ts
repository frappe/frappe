// What a bulk act's reply becomes: a toast when every record passed, the result panel on any failure, the tray for a background run.
import { toast } from "frappe-ui";
import { listDocuments, type BulkQueued, type BulkResult as InlineResult, type Envelope } from "@framework/ui/api";
import { shallowRef } from "vue";
import { __, __n } from "@/i18n";
import { followBulkRun, type BulkRecordRef, type BulkResult } from "./bulkRuns";
import { bulkTrayShown } from "./bulkTrayFlag";

const SETTLE_POLL_MS = 3000;

export interface BulkRef {
	name: string;
	doctype?: string;
}

export interface BulkFailed extends BulkRef {
	error: string;
}

/** What the result panel shows: one run's records by outcome. */
export interface BulkReport {
	label: string;
	doctype: string;
	total: number;
	done: BulkRef[];
	failed: BulkFailed[];
	queued: BulkRef[];
	/** A print run's merged PDF. */
	fileUrl?: string;
	/** Re-runs the same act on these names. */
	retry?: (names: string[]) => Promise<void>;
	/** Puts these names in the list selection. */
	select?: (names: string[]) => void;
}

export interface BulkRunOptions {
	label: string;
	doctype: string;
	/** Sends the act: on its original selection, or on `names` when retrying the failed ones. */
	send: (names?: string[]) => Promise<Envelope<InlineResult | BulkQueued>>;
	select?: (names: string[]) => void;
	/** A run ended (inline now, or in the background later): reload the list. */
	finished?: () => void;
}

/** The report the panel shows, or null while it is closed. */
export const bulkPanel = shallowRef<BulkReport | null>(null);
/** The retry and select each background run was started with, by task id. */
export const bulkRunMeta = new Map<string, Pick<BulkRunOptions, "label" | "doctype"> & Partial<BulkReport>>();

/** Sends a bulk act and routes its reply: the tray follows a background run, a failure opens the panel. */
export async function runBulk(options: BulkRunOptions, names?: string[]): Promise<void> {
	const { data } = await options.send(names);
	bulkTrayShown.value = true;
	const retry = (failed: string[]) => runBulk(options, failed);
	if ("task_id" in data) {
		bulkRunMeta.set(data.task_id, { label: options.label, doctype: options.doctype, retry, select: options.select });
		followBulkRun(data.task_id, () => options.finished?.());
		toast.info(__("{0} is running in the background", [options.label]));
		return;
	}
	options.finished?.();
	const report = reportOf(data, options, retry);
	if (report.failed.length) bulkPanel.value = report;
	else announceInline(report);
}

/** The report of a background run that settled, for the tray's "View". */
export function reportOfRun(taskId: string, label: string, result: BulkResult): BulkReport {
	const meta = bulkRunMeta.get(taskId);
	return {
		label: meta?.label ?? label,
		doctype: meta?.doctype ?? "",
		total: result.total,
		done: result.done.map(refOf),
		failed: result.failed.map(({ name, doctype, error }) => ({ name, doctype, error })),
		queued: (result.queued ?? []).map(refOf),
		fileUrl: result.file_url,
		retry: meta?.retry,
		select: meta?.select,
	};
}

function reportOf(data: InlineResult, options: BulkRunOptions, retry: (names: string[]) => Promise<void>): BulkReport {
	return {
		label: options.label,
		doctype: options.doctype,
		total: data.total,
		done: data.done.map(refOf),
		failed: data.failed,
		queued: (data.queued ?? []).map(refOf),
		fileUrl: (data as { file_url?: string }).file_url,
		retry,
		select: options.select,
	};
}

function announceInline({ done, queued }: BulkReport) {
	if (done.length)
		toast.success(__n("{0} record done", "{0} records done", done.length, [done.length]));
	if (queued.length)
		toast.info(__n("{0} record queued", "{0} records queued", queued.length, [queued.length]));
}

function refOf(record: BulkRecordRef): BulkRef {
	return typeof record === "string" ? { name: record } : record;
}

/** Moves queued records the Submission Queue has finished into done or failed; true while some are still queued. */
export async function settleQueued(report: BulkReport): Promise<boolean> {
	const doctype = report.doctype || report.queued[0]?.doctype;
	if (!doctype || !report.queued.length) return false;
	const names = report.queued.map(({ name }) => name);
	const { data } = await listDocuments<{ ref_docname: string; status: string; exception?: string }>(
		"Submission Queue",
		{
			fields: ["ref_docname", "status", "exception"],
			filters: { ref_doctype: doctype, ref_docname: ["in", names] },
			order_by: "creation desc",
			limit: names.length * 2,
		}
	);
	const latest = new Map<string, { status: string; exception?: string }>();
	for (const row of data) if (!latest.has(row.ref_docname)) latest.set(row.ref_docname, row);
	const stillQueued: BulkRef[] = [];
	const done = [...report.done];
	const failed = [...report.failed];
	for (const record of report.queued) {
		const row = latest.get(record.name);
		if (row?.status === "Finished") done.push(record);
		else if (row?.status === "Failed")
			failed.push({ ...record, error: row.exception?.trim().split("\n").pop() || __("The submission failed.") });
		else stillQueued.push(record);
	}
	if (bulkPanel.value !== report) return false;
	bulkPanel.value = { ...report, done, failed, queued: stillQueued };
	return stillQueued.length > 0;
}

export { SETTLE_POLL_MS };
