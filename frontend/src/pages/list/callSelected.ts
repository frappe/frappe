// `page.callSelected`: a script's whitelisted record function run on the selection through the bulk runner.
import { bulkCallDocuments, isBulkQueued, type BulkResult, type BulkSelection } from "@framework/ui/api";
import { toast } from "frappe-ui";
import { __, __n } from "@/i18n";
import { errorMessage } from "@/recordPage/errorMessage";
import { followBulkRun } from "@/shell/bulkRuns";

interface Run {
  doctype: string;
  selected: () => BulkSelection;
  reload: () => void;
}

/** Resolves `true` when the run was accepted or every record passed; a refusal shows its own toast. */
export async function callSelected(host: Run, method: string, args?: Record<string, unknown>): Promise<boolean> {
  const selected = host.selected();
  if (selected.names && !selected.names.length) {
    toast.error(__("Select records first"));
    return false;
  }
  try {
    const { data } = await bulkCallDocuments(host.doctype, { ...selected, method, args });
    if (!isBulkQueued(data)) return report(host, data);
    followBulkRun(data.task_id, host.reload);
    toast.info(__("Running in the background"));
    return true;
  } catch (error) {
    toast.error(errorMessage(error));
    return false;
  }
}

function report(host: Run, { done, failed, queued }: BulkResult): boolean {
  host.reload();
  if (queued?.length) toast.info(__n("{0} record queued", "{0} records queued", queued.length, [queued.length]));
  if (!failed.length) {
    toast.success(__n("{0} record done", "{0} records done", done.length, [done.length]));
    return true;
  }
  toast.error(__("{0} done, {1} failed: {2}", [done.length, failed.length, `${failed[0].name}: ${failed[0].error}`]));
  return false;
}
