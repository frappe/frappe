/** Translate through Frappe's global `__` when the host page has it, else fill the
 *  `{0}` placeholders so the English string still reads (as AutomationCanvas does). */
export function translate(message: string, args: unknown[] = []): string {
  const __ = (globalThis as { __?: (m: string, a?: unknown[]) => string }).__;
  if (__) return __(message, args);
  return message.replace(/\{(\d+)\}/g, (match, index) =>
    String(args[Number(index)] ?? match)
  );
}
