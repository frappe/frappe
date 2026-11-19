/** Rich-text HTML read without an editor: as plain text, and whether it holds anything. */

const BLOCK_TAGS = new Set([
  "ADDRESS",
  "ARTICLE",
  "BLOCKQUOTE",
  "DD",
  "DIV",
  "DL",
  "DT",
  "FIGCAPTION",
  "FIGURE",
  "FOOTER",
  "H1",
  "H2",
  "H3",
  "H4",
  "H5",
  "H6",
  "HEADER",
  "HR",
  "LI",
  "OL",
  "P",
  "PRE",
  "SECTION",
  "TABLE",
  "TR",
  "UL",
]);

/** The text of `html`, entities decoded, with a line break at each block and `<br>`. */
export function htmlToText(html: string | null | undefined): string {
  if (!html) return "";
  const body = new DOMParser().parseFromString(html, "text/html").body;
  return collect(body)
    .replace(/[ \t ]*\n[ \t ]*/g, "\n")
    .replace(/\n{2,}/g, "\n")
    .trim();
}

function collect(node: Node): string {
  if (node.nodeType === Node.TEXT_NODE) return node.textContent ?? "";
  if (!(node instanceof Element)) return "";
  if (node.tagName === "BR") return "\n";
  const inner = [...node.childNodes].map(collect).join("");
  if (node.tagName === "TD" || node.tagName === "TH") return `${inner} `;
  return BLOCK_TAGS.has(node.tagName) ? `\n${inner}\n` : inner;
}

/** Whether `html` shows nothing: no text and no image, video or embed. */
export function isEmptyHtml(html: string | null | undefined): boolean {
  if (!html) return true;
  const doc = new DOMParser().parseFromString(html, "text/html");
  if (doc.querySelector("img, video, iframe, embed, object")) return false;
  return (doc.body.textContent ?? "").trim().length === 0;
}
