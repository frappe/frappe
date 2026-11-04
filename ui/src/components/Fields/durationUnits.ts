import type { DurationUnits } from "frappe-ui";
import type { FieldMeta } from "./types";

/** The units a Duration shows, as desk v1 does: days unless `hide_days`, seconds unless `hide_seconds`. */
export function durationUnits(field: FieldMeta): DurationUnits {
  return {
    largestUnit: field.hideDays ? "hour" : "day",
    smallestUnit: field.hideSeconds ? "minute" : "second",
  };
}
