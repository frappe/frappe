import DOMPurify from "dompurify";

/**
 * Sanitize an HTML string for safe binding via `v-html`.
 *
 * Notification `title`/`description` are rendered HTML (backfilled from email templates or
 * System Notification rules) that can embed user-controlled document-field values through Jinja
 * — e.g. `<img src=x onerror="...">`. DOMPurify keeps benign formatting (`<b>`, links, etc.)
 * while stripping scripts and event-handler attributes, so the markup renders without executing.
 */
export function sanitizeHtml(html: string | null | undefined): string {
  if (!html) return "";
  return DOMPurify.sanitize(html);
}
