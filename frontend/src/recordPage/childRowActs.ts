// The `record` surface's child-row acts. A row is `{table, idx}`, the 1-based number the grid shows.
import type { ActEntry } from "@/acts/dispatcher";
import { holdsChildRows, identify, rowKey } from "@framework/ui/fields";
import type { RowAddress } from "@framework/ui/fields/types";
import { evaluateDependsOn, mapField, newRowValues } from "@framework/ui/FormLayout";
import { NO_VALUE } from "@framework/ui/FormLayout/noValueFields";
import type { RawMetaField } from "@framework/ui/FormLayout/types";
import { changed, coerce, refuse } from "./recordActs";
import type { PageField } from "./types";

type Row = Record<string, any>;
type Values = Record<string, unknown>;

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
}

interface Table {
  name: string;
  columns: RawMetaField[];
  rows: Row[];
  field: PageField;
}

export function childRowEntries(host: RowHost): ActEntry[] {
  const acts = new ChildRowActs(host);
  const entry = (name: string, run: (value: any) => unknown): ActEntry => ({
    item: { name, palette: false, run: (_page, value) => run(value) },
    hidden: false,
  });
  return [
    entry("add_child_row", (value) => acts.add(value)),
    entry("set_child_values", (value) => acts.set(value)),
    entry("remove_child_row", (value) => acts.remove(value)),
  ];
}

class ChildRowActs {
  constructor(private host: RowHost) {}

  async add({ table, values = {} }: { table: string; values?: Values }) {
    const act = "record.add_child_row";
    const found = this.table(act, table);
    refuse(act, found.field.cannot_add_rows ? `${table} does not allow new rows` : undefined);
    const row = identify(newRowValues(found.columns.map((column) => mapField(column, {}))));
    for (const fieldname of Object.keys(values)) refuse(act, this.cannotSet(found, row, fieldname));
    found.rows.push(row);
    const live = found.rows[found.rows.length - 1];
    await this.host.rowChanged(this.address(table, live), "add");
    refuse(act, found.rows.includes(live) ? undefined : `an onAdd handler removed the new row of ${table}`);
    await this.fill(found, live, values);
    return { idx: found.rows.indexOf(live) + 1, values: visible(live), errors: this.host.errors() };
  }

  async set({ table, idx, values }: { table: string; idx: number; values: Values }) {
    const act = "record.set_child_values";
    const found = this.table(act, table);
    const row = this.row(act, found, idx);
    for (const fieldname of Object.keys(values)) refuse(act, this.cannotSet(found, row, fieldname));
    const before = { ...row };
    await this.fill(found, row, values);
    return { values: changed(before, row), errors: this.host.errors() };
  }

  async remove({ table, idx }: { table: string; idx: number }) {
    const act = "record.remove_child_row";
    const found = this.table(act, table);
    const row = this.row(act, found, idx);
    refuse(act, found.field.cannot_delete_rows ? `${table} does not allow removing rows` : undefined);
    const address = this.address(table, row);
    found.rows.splice(idx - 1, 1);
    await this.host.rowChanged(address, "remove");
    return { rows: found.rows.length };
  }

  private async fill(found: Table, row: Row, values: Values) {
    for (const [fieldname, value] of Object.entries(values)) {
      row[fieldname] = coerce(found.columns.find((column) => column.fieldname === fieldname)!.fieldtype, value);
      await this.host.commit(fieldname, this.address(found.name, row));
    }
  }

  private table(act: string, name: string): Table {
    const field = this.host.field(name);
    refuse(act, !field || !holdsChildRows(field.fieldtype) ? `${name} is not a table of this form` : undefined);
    refuse(act, field!.hidden ? `${name} is hidden now` : field!.read_only ? `${name} is read-only` : undefined);
    const doc = this.host.doc();
    if (!Array.isArray(doc[name])) doc[name] = [];
    const columns = this.host.childFields(String(field!.options));
    refuse(act, columns ? undefined : `the columns of ${name} are not loaded yet`);
    return { name, columns: columns!, rows: doc[name], field: field! };
  }

  private row(act: string, { name, rows }: Table, idx: number): Row {
    refuse(act, rows[idx - 1] ? undefined : `${name} has ${rows.length} rows; idx must be 1 to ${rows.length}`);
    return rows[idx - 1];
  }

  private cannotSet({ name, columns }: Table, row: Row, fieldname: string): string | undefined {
    const column = columns.find((one) => one.fieldname === fieldname);
    if (!column || NO_VALUE.has(column.fieldtype) || holdsChildRows(column.fieldtype))
      return `${fieldname} is not a column of ${name} that can be set`;
    const doc = this.host.doc();
    // A script's override of the column (`page.fields.update("<table>.<column>", …)`) counts as the grid counts it.
    const override = this.host.field(`${name}.${fieldname}`);
    if (column.hidden || override?.hidden || !evaluateDependsOn(column.depends_on, row, doc)) return `${fieldname} is hidden now`;
    const locked = column.read_only_depends_on && evaluateDependsOn(column.read_only_depends_on, row, doc);
    if (column.read_only || override?.read_only || column.fieldtype === "Read Only" || locked) return `${fieldname} is read-only`;
  }

  private address(parentfield: string, row: Row): RowAddress {
    return { parentfield, key: rowKey(identify(row))! };
  }
}

/** The row's own fields, without the client's bookkeeping. */
function visible(row: Row): Values {
  return Object.fromEntries(Object.entries(row).filter(([key]) => !key.startsWith("__")));
}
