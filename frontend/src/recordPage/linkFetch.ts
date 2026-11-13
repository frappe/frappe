// Desk v1's `validate_link_and_fetch` on a Link's change: the value is checked against
// the field's `link_filters`, and each field whose `fetch_from` names the Link is copied.
import { runMethod } from "@framework/ui/api";
import { holdsChildRows, rowKey } from "@framework/ui/fields";
import { resolveLinkFilters, type LinkFilters } from "@framework/ui/FormLayout";
import type { RawMetaField } from "@framework/ui/FormLayout/types";
import type { RowAddress } from "@framework/ui/fields/types";
import type { FieldErrors } from "./fieldErrors";

type Values = Record<string, any>;

export interface LinkFetchHost {
  doc: () => Values;
  fields: () => RawMetaField[] | undefined;
  childFields?: (doctype: string) => RawMetaField[] | undefined;
  errors: FieldErrors;
}

/**
 * `{ target: source }` for the fields fetched from `link`. A `fetch_if_empty` field
 * that holds a value keeps it, so it is left out.
 */
export function fetchTargets(fields: RawMetaField[], link: string, record: Values): Record<string, string> {
  const targets: Record<string, string> = {};
  for (const field of fields) {
    const [source, fetched] = field.fetch_from?.split(".") ?? [];
    if (source !== link || !fetched) continue;
    if (field.fetch_if_empty && !isEmpty(record[field.fieldname])) continue;
    targets[field.fieldname] = fetched;
  }
  return targets;
}

export class LinkFetch {
  constructor(private host: LinkFetchHost) {}

  /**
   * Runs on a field's commit. A field that is no Link, or has neither filters nor
   * fetches, gets no promise: awaiting one would let an overlapping edit's handler run first.
   */
  run(fieldname: string, row?: RowAddress): Promise<void> | undefined {
    const fields = row ? this.childFields(row.parentfield) : this.host.fields();
    const field = fields?.find((one) => one.fieldname === fieldname);
    const record = this.record(row);
    if (!fields || field?.fieldtype !== "Link" || !field.options || !record) return;

    const targets = fetchTargets(fields, fieldname, record);
    const filters = resolveLinkFilters(field.link_filters, record, this.host.doc());
    if (!filters && !Object.keys(targets).length) return;
    return this.apply(field.options, fieldname, record[fieldname], targets, filters, row);
  }

  private async apply(
    doctype: string,
    fieldname: string,
    value: any,
    targets: Record<string, string>,
    filters: LinkFilters | undefined,
    row?: RowAddress
  ): Promise<void> {
    const found = value ? await validateLink(doctype, value, targets, filters) : {};
    // A later edit, or a removed row, makes this answer stale.
    const current = this.record(row);
    if (!current || current[fieldname] !== value) return;

    if (value && !found.name) {
      current[fieldname] = null;
      this.host.errors.mark(
        row ? { ...row, fieldname } : fieldname,
        `${value} does not match this field's filters`
      );
    }
    for (const [target, source] of Object.entries(targets)) {
      current[target] = found.name ? found[source] ?? null : null;
    }
  }

  private record(row?: RowAddress): Values | undefined {
    const doc = this.host.doc();
    if (!row) return doc;
    const table = doc?.[row.parentfield];
    return Array.isArray(table) ? table.find((one) => rowKey(one) === row.key) : undefined;
  }

  private childFields(parentfield: string): RawMetaField[] | undefined {
    const table = this.host.fields()?.find((one) => one.fieldname === parentfield);
    return table?.options && holdsChildRows(table.fieldtype)
      ? this.host.childFields?.(table.options)
      : undefined;
  }
}

// POST: v1 caches only a call with nothing to fetch, and the filters may be too long for a URL.
async function validateLink(
  doctype: string,
  docname: string,
  targets: Record<string, string>,
  filters: LinkFilters | undefined
): Promise<Values> {
  const { data } = await runMethod<Values>("frappe.client.validate_link_and_fetch", {
    doctype,
    docname,
    fields_to_fetch: Object.values(targets),
    filters,
  });
  return data ?? {};
}

function isEmpty(value: unknown): boolean {
  return value == null || value === "";
}
