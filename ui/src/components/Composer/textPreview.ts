const PREVIEW_WORD_COUNT = 2;

/** Short plain-text preview of editor HTML, for the collapsed trigger bar.
 *  Empty when the body carries no text (images/attachments only still count
 *  as content, but have nothing to preview). */
export function textPreview(html: string): string {
  if (!html) return "";
  const doc = new DOMParser().parseFromString(html, "text/html");
  const words = (doc.body.textContent ?? "")
    .trim()
    .split(/\s+/)
    .filter(Boolean);
  if (!words.length) return "";
  const preview = words.slice(0, PREVIEW_WORD_COUNT).join(" ");
  return words.length > PREVIEW_WORD_COUNT ? `${preview}...` : preview;
}
