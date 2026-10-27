import { inject } from "vue";
import { displayValue } from "./displayValue";
import { getFormatDefaults, resolvePrecision } from "./formatDefaults";
import { resolveFieldCurrency, useDocValueReader } from "./resolveCurrency";
import type { RecordContext } from "./pickSiblingValue";
import { LinkTitlesKey } from "../Fields/types";
import type { FieldMeta } from "../Fields/types";

/** Formats `value` of `field` for display; see `useFieldDisplay`. */
export type FieldDisplay = (
  field: FieldMeta,
  value: unknown,
  records?: RecordContext
) => string;

/** `displayValue` bound to the site's format defaults, a Currency field's resolved
 *  currency and the host's link titles. `records` holds the document, and the row and
 *  parent document of a child-table field. Call it in `setup`; the formatter it
 *  returns is reactive inside a computed. */
export function useFieldDisplay(): FieldDisplay {
  const titles = inject(LinkTitlesKey, null);
  const getDocValue = useDocValueReader();
  return (field, value, records = {}) => {
    const defaults = getFormatDefaults();
    return displayValue(value, field, {
      precision: resolvePrecision(field),
      currency:
        field.fieldtype === "Currency"
          ? resolveFieldCurrency(field.options, {
              ...records,
              defaultCurrency: defaults.currency,
              getDocValue,
            })
          : undefined,
      numberFormat: defaults.number_format,
      roundingMethod: defaults.rounding_method,
      doc: records.row ?? records.doc ?? undefined,
      linkTitles: titles?.value,
    });
  };
}
