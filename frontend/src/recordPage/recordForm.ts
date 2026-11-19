// The record page's form as the `record` acts drive it: values commit through the channel typing uses.
import type { ActEntry } from "@/acts/dispatcher";
import { rowKey } from "@framework/ui/fields";
import { layoutFields, resolveFieldConditionals } from "@framework/ui/FormLayout";
import type { RowAddress } from "@framework/ui/fields/types";
import type { FormLayoutSchema, RawMetaField } from "@framework/ui/FormLayout/types";
import { childRowEntries, type RowHost } from "./childRowActs";
import type { RecordCommitChannel } from "./commitChannel";
import type { FieldErrors } from "./fieldErrors";
import { setValuesEntry, type ValueForm } from "./recordActs";
import { shownFields } from "./requiredFields";
import type { RecordPageApi } from "./types";

export interface RecordFormHost {
  page: RecordPageApi;
  commits: RecordCommitChannel;
  errors: FieldErrors;
  childFields?: (doctype: string) => RawMetaField[] | undefined;
  /** The Details layout the reader sees: a field in a hidden tab or section is not one to fill. */
  formLayout?: () => FormLayoutSchema | undefined;
}

/** The four acts that fill a record's form. */
export function recordEntries(host: RecordFormHost): ActEntry[] {
  const form = new RecordForm(host);
  return [setValuesEntry(form), ...childRowEntries(form)];
}

export class RecordForm implements ValueForm, RowHost {
  constructor(private host: RecordFormHost) {}

  doc = () => this.host.page.doc;

  field(fieldname: string) {
    const { fields } = this.host.page;
    const field = fields.has(fieldname) ? fields.get(fieldname) : null;
    return field && { ...field, hidden: field.hidden || this.offLayout(fieldname) };
  }

  /** The cell as the grid resolves it, or undefined when no layout holds its table. */
  cell(table: string, row: Record<string, any>, fieldname: string) {
    const column = this.shown().find((one) => one.fieldname === table)?.childFields?.find((one) => one.fieldname === fieldname);
    if (!column) return undefined;
    const { hidden, readOnly } = resolveFieldConditionals(column, row, this.doc());
    return { hidden: !!hidden, readOnly: !!readOnly };
  }

  childFields = (doctype: string) => this.host.childFields?.(doctype);

  async commit(fieldname: string, row?: RowAddress) {
    const { commits } = this.host;
    const value = this.record(row)?.[fieldname];
    // Not `flush`: it waits on every running handler, the one that called this act included.
    // `pending` answers false for an echo of the last commit; the page's wrapper answers nothing otherwise.
    if (commits.pending(fieldname, value, row) !== false) await commits.commit(fieldname, value, row);
  }

  async rowChanged(row: RowAddress, change: "add" | "remove") {
    await this.host.commits.rowChanged(row, change);
  }

  errors() {
    return Object.fromEntries(
      Object.entries(this.host.errors.current()).map(([key, message]) => [this.nameOf(key), [message].flat().join("; ")]),
    );
  }

  /** The top-level fields the form shows now, in order. */
  shown() {
    const layout = this.host.formLayout?.();
    return layout ? shownFields(layout, this.doc()) : [];
  }

  private offLayout(fieldname: string) {
    const layout = this.host.formLayout?.();
    if (!layout || !layoutFields(layout).some((one) => one.fieldname === fieldname)) return false;
    return !this.shown().some((one) => one.fieldname === fieldname);
  }

  private record(row?: RowAddress): Record<string, any> | undefined {
    const doc = this.doc();
    return row ? doc[row.parentfield]?.find((one: Record<string, any>) => rowKey(one) === row.key) : doc;
  }

  /** A cell's mark is keyed by its row's key; the caller knows the row by its number. */
  private nameOf(key: string) {
    if (!key.startsWith("[")) return key;
    const [table, row, fieldname] = JSON.parse(key) as [string, string, string];
    const idx = (this.doc()[table] ?? []).findIndex((one: Record<string, any>) => rowKey(one) === row);
    return `${table}.${idx + 1}.${fieldname}`;
  }
}
