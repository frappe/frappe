/** The trailing path segment of a file URL, as a person would name the file; the URL itself when it has none. */
export function fileName(url: unknown): string {
  if (!url) return "";
  try {
    const path = new URL(String(url), "http://x").pathname;
    return decodeURIComponent(path.split("/").filter(Boolean).pop() || String(url));
  } catch {
    return String(url);
  }
}
