// The `record` surface's child-row acts. A row is `{table, idx}`, the 1-based number the grid shows.
// The runs sit in `childRowRuns`, loaded on the first run, so the record page's first paint does not carry them.
import type { ActEntry } from "@/acts/dispatcher";
import type { RowAddress } from "@framework/ui/fields/types";
import type { RawMetaField } from "@framework/ui/FormLayout/types";
import type { PageField } from "./types";
import type { ChildRowActs } from "./childRowRuns";

type Row = Record<string, any>;

/** The page as the child-row acts use it. */
export interface RowHost {
  doc: () => Row;
  /** The table field as it now resolves, or null when the form has none of that name. */
  field: (fieldname: string) => PageField | null;
  childFields: (doctype: string) => RawMetaField[] | undefined;
  /** Commits a cell the way typing does, and waits for its handlers. */
  commit: (fieldname: string, row: RowAddress) => Promise<void>;
  /** Fires `onAdd` or `onRemove` and waits for the handlers. */
  rowChanged: (row: RowAddress, change: "add" | "remove") => Promise<void>;
  errors: () => Record<string, string>;
  /** Whether the grid hides or locks the cell, when the form's layout holds the table. */
  cell?: (table: string, row: Row, fieldname: string) => { hidden: boolean; readOnly: boolean } | undefined;
}

export function childRowEntries(host: RowHost): ActEntry[] {
  const runner = () => import("./childRowRuns").then(({ ChildRowActs }) => new ChildRowActs(host));
  const entry = (name: string, run: (acts: ChildRowActs, value: any) => unknown): ActEntry => ({
    item: {
      name,
      palette: false,
      run: async (_page, value) => run(await runner(), value),
    },
    hidden: false,
  });
  return [
    entry("add_child_row", (acts, value) => acts.add(value)),
    entry("set_child_values", (acts, value) => acts.set(value)),
    entry("remove_child_row", (acts, value) => acts.remove(value)),
  ];
}
