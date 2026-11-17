// The List renderer's own acts: its columns, page size and Load More. Their runs load on first use.
import type { ActEntry } from "@/acts/dispatcher";
import { __ } from "@/i18n";
import type { ListView } from "@/list/useListView";

/** Load More is unavailable, like its button, when no next page is left. */
export function listViewEntries(view: ListView): ActEntry[] {
  const labels = { set_columns: __("Set Columns"), set_page_size: __("Set Page Size"), load_more: __("Load More") };
  return Object.entries(labels).map(([name, label]) => ({
    item: {
      name,
      label,
      palette: false,
      run: async (_context: unknown, value: unknown) => (await import("./listViewRuns")).RUNS[name](view, value),
    },
    hidden: name === "load_more" && !view.hasNextPage.value,
  }));
}
