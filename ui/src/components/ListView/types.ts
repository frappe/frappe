import type { DoctypeMeta } from "../../composables/useDoctypeMeta";

/** Props for `<ListViewShell>`. */
export interface ListViewShellProps {
  /** Doctype whose Meta drives the shell's fields/columns. */
  doctype: string;
}

/** Scope shared by the shell's slots. */
interface ListViewShellSlotScope {
  doctype: string;
  meta: DoctypeMeta | null;
}

export interface ListViewShellSlots {
  /** Replaces the toolbar region (controls, actions). */
  toolbar?: (props: ListViewShellSlotScope & { loading: boolean }) => any;
  /** Replaces the table/body region. */
  table?: (props: ListViewShellSlotScope) => any;
  /** Replaces the footer region (pagination, counts). */
  footer?: (props: ListViewShellSlotScope) => any;
}
