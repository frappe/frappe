import { inject } from "vue";
import { displayValue } from "./displayValue";
import { getFormatDefaults } from "./formatDefaults";
import { resolveFieldCurrency, useDocValueReader } from "./resolveCurrency";
import { LinkTitlesKey } from "../Fields/types";
import type { FieldMeta } from "../Fields/types";

/** Formats a field of `doc` for display; see `useFieldDisplay`. */
export type FieldDisplay = (field: FieldMeta, doc: Record<string, any>) => string;

/**
 * A formatter bound to the host: the site's number format and rounding, a Currency
 * field's resolved currency, and the host's link titles (`LinkTitlesKey`). Call it
 * in `setup`; the returned function reads reactive state, so a computed that calls
 * it re-runs when the record, the titles or the format defaults change.
 */
export function useFieldDisplay(): FieldDisplay {
  const titles = inject(LinkTitlesKey, null);
  const getDocValue = useDocValueReader();
  return (field, doc) => {
    const defaults = getFormatDefaults();
    return displayValue(doc[field.fieldname], field, {
      precision: field.precision,
      currency:
        field.fieldtype === "Currency"
          ? resolveFieldCurrency(field.options, {
              doc,
              defaultCurrency: defaults.currency,
              getDocValue,
            })
          : undefined,
      numberFormat: defaults.number_format,
      roundingMethod: defaults.rounding_method,
      doc,
      linkTitles: titles?.value,
    });
  };
}
