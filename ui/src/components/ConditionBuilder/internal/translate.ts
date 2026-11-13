/**
 * Read off the global at call time: this package has no i18n of its own. Values
 * go through `{0}`, since a sentence glued from translated halves only reads in
 * English.
 */
export function t(message: string, replace?: unknown[]): string {
  const translate = (
    globalThis as { __?: (m: string, r?: unknown[]) => string }
  ).__;
  if (typeof translate === "function") return translate(message, replace);
  if (!replace) return message;
  // The fallback substitutes too, or a literal `{0}` is read out on a host with
  // no plugin.
  return message.replace(/\{(\d+)\}/g, (match, index) => {
    const value = replace[Number(index)];
    return value === undefined ? match : String(value);
  });
}
