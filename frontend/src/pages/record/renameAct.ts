// `header.rename`, the `⋯` menu's "Rename…", and the `page.rename` it runs. The dialog's run sits in `renameRun`, loaded on the first run.
import { toast } from "frappe-ui";
import { renameDocument } from "@framework/ui/api";
import { __ } from "@/i18n";
import { errorMessage, type HeaderItem, type RecordPageApi } from "@/recordPage";
import { routeFor } from "@/router/routeFor";
import { stripTags } from "./saveResponse";

export function renameItem(): HeaderItem {
  return {
    name: "rename",
    asks: ["dialog", "danger"],
    label: __("Rename…"),
    icon: "lucide-pencil",
    group: "assign_band",
    right: "write",
    run: async (page) => (await import("./renameRun")).openRename(page),
  };
}

/** Saves a dirty draft, then renames and replaces the address while `onRecord` holds; `null` when refused. */
export async function renameRecord(
  page: RecordPageApi,
  name: string,
  merge: boolean,
  onRecord: () => boolean
): Promise<string | null> {
  if (!(await page.save()) || !onRecord()) return null;
  let renamed: string;
  try {
    ({ data: renamed } = await renameDocument(page.doctype, page.docname, name, { merge }));
  } catch (exception) {
    toast.error(stripTags(errorMessage(exception)));
    return null;
  }
  if (!onRecord()) return renamed;
  // The old name is gone, so a reader who keeps edits made meanwhile is told where the record went.
  const refused = await page.router.replace(routeFor(page.doctype, renamed));
  if (refused) toast.error(__("Renamed to {0}; this page still shows the old name", [renamed]));
  else toast.success(__("Renamed"));
  return renamed;
}
