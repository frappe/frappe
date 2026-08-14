// What you can do to one script. Two menus render this: the rail's row `⋯`,
// which is the only way to reach a script you have not opened, and the header's
// `⋯`, which is the same menu addressed to the one you have (ticket 37,
// amendment 4). One definition, so the two cannot offer different things.
import type { PageScriptDoc } from "./pageScriptApi";

export interface RowActionHandlers {
  toggleEnabled: (row: PageScriptDoc) => void;
  duplicate: (row: PageScriptDoc) => void;
  remove: (row: PageScriptDoc) => void;
}

/**
 * Enable/Disable is here rather than on the row itself because the dimmed label
 * that states it has no affordance of its own — state and the way to change it
 * end up one hop apart (ticket 37, round 4).
 */
export function rowActions(
  row: PageScriptDoc,
  handlers: RowActionHandlers,
  /** A write is in flight, so nothing new may be started. */
  busy = false,
) {
  return [
    {
      label: row.enabled ? "Disable" : "Enable",
      icon: row.enabled ? "lucide-circle-slash" : "lucide-circle-check",
      onClick: () => handlers.toggleEnabled(row),
    },
    {
      label: "Duplicate",
      icon: "lucide-copy",
      onClick: () => handlers.duplicate(row),
    },
    {
      label: "Delete…",
      icon: "lucide-trash-2",
      theme: "red",
      onClick: () => handlers.remove(row),
    },
  ].map((option) => ({ ...option, disabled: busy }));
}
