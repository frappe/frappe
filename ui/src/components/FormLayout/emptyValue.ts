// Its own module: `resolveLayout` is in the shell, and `displayValue` would pull formatting in.
/** Whether a value reads as unset — `null`, blank, or an empty child table. */
export function isEmptyValue(value: unknown): boolean {
  if (Array.isArray(value)) return value.length === 0;
  return value == null || value === "";
}
