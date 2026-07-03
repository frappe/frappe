/** Plain-text preview of editor HTML, for the collapsed trigger bar. Strips
 *  markup and collapses whitespace only — the caller renders it in a `truncate`
 *  (or similar) container, so clipping to one line and adding the ellipsis is
 *  CSS's job, not this function's. Empty when the body carries no text
 *  (images/attachments only still count as content, but have nothing to
 *  preview). */
export function textPreview(html: string): string {
  if (!html) return "";
  const doc = new DOMParser().parseFromString(html, "text/html");
  return (doc.body.textContent ?? "").trim().replace(/\s+/g, " ");
}
