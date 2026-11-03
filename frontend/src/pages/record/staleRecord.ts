// A conflict on a record other than the page's own: a linked record in Cancel all, or one a hook saves.
import type { StaleDoc } from "@framework/ui/api";
import { __ } from "@/i18n";
import type { Confirm } from "./discardChanges";

/** The stale record when it is not the page's own; `null` for the page's record or an unnamed error. */
export function otherStaleRecord(
  stale: StaleDoc | undefined,
  doctype: string,
  name: string,
): StaleDoc | null {
  if (!stale) return null;
  if ("hidden" in stale) return stale;
  return stale.doctype === doctype && stale.name === name ? null : stale;
}

/** Says which record changed. The page's own record is not offered for reload: it is not the stale one. */
export async function showStaleRecord(
  confirm: Confirm,
  stale: StaleDoc,
  open: (doctype: string, name: string) => void,
): Promise<void> {
  if ("hidden" in stale) {
    await confirm({
      title: __("Another record changed"),
      message: __("Another record changed after you read it."),
      actions: [{ label: __("Close") }],
    });
    return;
  }
  await confirm({
    title: __("{0} changed", [__(stale.doctype)]),
    message: __(
      "{0} {1} changed after you read it. Open it to see its latest version, then try again.",
      [__(stale.doctype), stale.name],
    ),
    actions: [
      { label: __("Open {0}", [stale.name]), variant: "solid", onClick: () => open(stale.doctype, stale.name) },
      { label: __("Close") },
    ],
  });
}
