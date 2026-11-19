// Starts a bulk print; the shell's tray follows the run and offers the PDF when it settles.
import { bulkPrintDocuments, type BulkPrintBody } from "@framework/ui/api";
import { followBulkRun } from "@/shell/bulkRuns";

export async function startBulkPrint(doctype: string, body: BulkPrintBody) {
	const { data } = await bulkPrintDocuments(doctype, body);
	followBulkRun(data.task_id);
}
