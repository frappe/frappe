// `page.callSelected`: a script's whitelisted record function run on the selection through the bulk runner.
import { bulkCallDocuments } from "@framework/ui/api";
import type { BulkSelection } from "@framework/ui/api";
import { toast } from "frappe-ui";
import { __ } from "@/i18n";
import { errorMessage } from "@/recordPage/errorMessage";

interface Run {
  doctype: string;
  selected: () => BulkSelection;
  reload: () => void;
}

/** Resolves `true` once the runner took the request; the shell reports the outcome (toast, tray or result panel). */
export async function callSelected(host: Run, method: string, args?: Record<string, unknown>): Promise<boolean> {
  const selected = host.selected();
  if (selected.names && !selected.names.length) {
    toast.error(__("Select records first"));
    return false;
  }
  try {
    const { runBulk } = await import("@/shell/bulkOutcome");
    await runBulk({
      label: method.split(".").pop()!.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase()),
      doctype: host.doctype,
      send: (names) => bulkCallDocuments(host.doctype, { ...(names ? { names } : selected), method, args }),
      finished: host.reload,
    });
    return true;
  } catch (error) {
    toast.error(errorMessage(error));
    return false;
  }
}
