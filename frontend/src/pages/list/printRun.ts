// Starts a bulk print and offers its PDF when the run settles.
import { bulkPrintDocuments, type BulkPrintBody } from "@framework/ui/api";
import { toast } from "frappe-ui";
import { __ } from "@/i18n";
import { followBulkRun, type BulkRun } from "@/shell/bulkRuns";

const PDF_TOAST_MS = 20000;

export async function startBulkPrint(doctype: string, body: BulkPrintBody) {
	const { data } = await bulkPrintDocuments(doctype, body);
	followBulkRun(data.task_id, offerPdf);
}

function offerPdf(run: BulkRun) {
	const url = run.result?.file_url;
	if (!url) return;
	toast.success(__("Your PDF is ready"), {
		duration: PDF_TOAST_MS,
		action: { label: __("Open"), onClick: () => window.open(url, "_blank", "noopener") },
	});
}
