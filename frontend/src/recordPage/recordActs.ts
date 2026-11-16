// The `record` surface: acts that fill the form in front the way typing does, and never save.
// The run sits in `recordRuns`, loaded on the first run, so a page's first paint does not carry it.
import type { ActEntry } from "@/acts/dispatcher";

type Row = Record<string, any>;

/** What an act needs to know of a top-level field. */
export interface FormField {
  fieldtype: string;
  hidden?: boolean | 0 | 1;
  read_only?: boolean | 0 | 1;
}

/** The form in front, as `record.set_values` sees it. */
export interface ValueForm {
  doc: () => Row;
  /** The field as it now resolves, or null when the form has none of that name. */
  field: (fieldname: string) => FormField | null;
  /** Commits the value already written to the doc, as typing does, and waits for its handlers. */
  commit: (fieldname: string) => Promise<void>;
  /** The marks on screen: a field's name, or `table.<idx>.<fieldname>` for a cell. */
  errors: () => Record<string, string>;
}

export function setValuesEntry(form: ValueForm): ActEntry {
  return {
    item: {
      name: "set_values",
      palette: false,
      run: async (_form, value) => (await import("./recordRuns")).setValues(form, value.values),
    },
    hidden: false,
  };
}
