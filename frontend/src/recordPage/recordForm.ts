// The record page's form as the `record` acts drive it: values commit through the channel typing uses.
import type { ActEntry } from "@/acts/dispatcher";
import { rowKey } from "@framework/ui/fields";
import type { RowAddress } from "@framework/ui/fields/types";
import type { RawMetaField } from "@framework/ui/FormLayout/types";
import { childRowEntries, type RowHost } from "./childRowActs";
import type { RecordCommitChannel } from "./commitChannel";
import type { FieldErrors } from "./fieldErrors";
import { setValuesEntry, type ValueForm } from "./recordActs";
import type { RecordPageApi } from "./types";

export interface RecordFormHost {
  page: RecordPageApi;
  commits: RecordCommitChannel;
  errors: FieldErrors;
  childFields?: (doctype: string) => RawMetaField[] | undefined;
}

/** The four acts that fill a record's form. */
export function recordEntries(host: RecordFormHost): ActEntry[] {
  const form = new RecordForm(host);
  return [setValuesEntry(form), ...childRowEntries(form)];
}

class RecordForm implements ValueForm, RowHost {
  constructor(private host: RecordFormHost) {}

  doc = () => this.host.page.doc;

  field(fieldname: string) {
    const { fields } = this.host.page;
    return fields.has(fieldname) ? fields.get(fieldname) : null;
  }

  childFields = (doctype: string) => this.host.childFields?.(doctype);

  async commit(fieldname: string, row?: RowAddress) {
    const { commits } = this.host;
    const value = this.record(row)?.[fieldname];
    if (commits.pending(fieldname, value, row)) await commits.commit(fieldname, value, row);
    await commits.flush();
  }

  async rowChanged(row: RowAddress, change: "add" | "remove") {
    this.host.commits.rowChanged(row, change);
    await this.host.commits.flush();
  }

  errors() {
    return Object.fromEntries(
      Object.entries(this.host.errors.current()).map(([key, message]) => [this.nameOf(key), [message].flat().join("; ")]),
    );
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
