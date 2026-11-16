// The child-row acts' runs; `childRowActs` imports them when one first runs.
import { holdsChildRows, identify, rowKey } from "@framework/ui/fields";
import type { RowAddress } from "@framework/ui/fields/types";
import { evaluateDependsOn, mapField, newRowValues } from "@framework/ui/FormLayout";
import { NO_VALUE } from "@framework/ui/FormLayout/noValueFields";
import type { RawMetaField } from "@framework/ui/FormLayout/types";
import type { RowHost } from "./childRowActs";
import { changed, coerce, refuse } from "./recordRuns";
import type { PageField } from "./types";

type Row = Record<string, any>;
type Values = Record<string, unknown>;

interface Table {
  name: string;
  columns: RawMetaField[];
  rows: Row[];
  field: PageField;
}

export class ChildRowActs {
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
    const added = await this.fill(act, found, live, values);
    return { idx: this.rowsOf(found).indexOf(added) + 1, values: visible(added), errors: this.host.errors() };
  }

  async set({ table, idx, values }: { table: string; idx: number; values: Values }) {
    const act = "record.set_child_values";
    const found = this.table(act, table);
    const row = this.row(act, found, idx);
    for (const fieldname of Object.keys(values)) refuse(act, this.cannotSet(found, row, fieldname));
    const before = { ...row };
    const after = await this.fill(act, found, row, values);
    return { values: changed(before, after), errors: this.host.errors() };
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

  /** Sets each value on the row, found again by its key after every handler; refuses once one removed it. */
  private async fill(act: string, found: Table, row: Row, values: Values): Promise<Row> {
    const key = rowKey(identify(row));
    const live = () => {
      const current = this.rowsOf(found).find((one) => rowKey(one) === key);
      refuse(act, current ? undefined : `a handler removed the row of ${found.name}`);
      return current!;
    };
    let current = live();
    for (const [fieldname, value] of Object.entries(values)) {
      current[fieldname] = coerce(found.columns.find((column) => column.fieldname === fieldname)!.fieldtype, value);
      await this.host.commit(fieldname, this.address(found.name, current));
      current = live();
    }
    return current;
  }

  private rowsOf({ name }: Table): Row[] {
    const rows = this.host.doc()[name];
    return Array.isArray(rows) ? rows : [];
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
    const cell = this.host.cell?.(name, row, fieldname);
    if (cell) return cell.hidden ? `${fieldname} is hidden now` : cell.readOnly ? `${fieldname} is read-only` : undefined;
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
