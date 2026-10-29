/** Code blocks in stored rich text drawn as the editor draws them, without loading the editor. */
import type { ElementContent } from "hast";
import type { createLowlight } from "lowlight";

export type Highlighter = ReturnType<typeof createLowlight>;

let loading: Promise<Highlighter> | undefined;

/** The highlighter and its colours, fetched once, on the first code block. */
export function loadHighlighter(): Promise<Highlighter> {
  loading ??= import("./highlighter").then((module) => module.highlighter);
  return loading;
}

export function hasCodeBlock(html: string | null | undefined): boolean {
  return Boolean(html && /<pre[\s>]/i.test(html));
}

/**
 * `html` with a line-number gutter in each `<pre>`, and its code highlighted when a
 * `highlighter` is given. Parsed in a detached document, so the caller still sanitises the result.
 */
export function drawCodeBlocks(html: string, highlighter: Highlighter | null): string {
  const doc = new DOMParser().parseFromString(html, "text/html");
  for (const pre of doc.body.querySelectorAll("pre")) drawCodeBlock(pre, highlighter);
  return doc.body.innerHTML;
}

function drawCodeBlock(pre: HTMLPreElement, highlighter: Highlighter | null) {
  const code = codeOf(pre);
  const text = code.textContent ?? "";
  if (highlighter) code.replaceChildren(...highlight(highlighter, code, text));
  pre.classList.add("code-block");
  pre.prepend(lineNumbers(pre.ownerDocument, text.split("\n").length));
}

// Desk v1 stored a bare `<pre>`; the editor parses that as a code block too.
function codeOf(pre: HTMLPreElement): HTMLElement {
  const code = pre.querySelector("code");
  if (code) return code;
  const wrapped = pre.ownerDocument.createElement("code");
  wrapped.append(...pre.childNodes);
  pre.append(wrapped);
  return wrapped;
}

function languageOf(code: HTMLElement): string | null {
  return code.className.match(/(?:^|\s)language-(\S+)/)?.[1] ?? null;
}

// The editor's rule: a known language highlights as itself, anything else is detected.
function highlight(highlighter: Highlighter, code: HTMLElement, text: string): Node[] {
  const language = languageOf(code);
  const tree =
    language && highlighter.registered(language)
      ? highlighter.highlight(language, text)
      : highlighter.highlightAuto(text);
  return toNodes(code.ownerDocument, tree.children as ElementContent[]);
}

function lineNumbers(doc: Document, count: number): HTMLElement {
  const gutter = doc.createElement("span");
  gutter.className = "code-block-lines";
  gutter.setAttribute("aria-hidden", "true");
  for (let n = 1; n <= count; n++) {
    const line = doc.createElement("span");
    line.textContent = String(n);
    gutter.append(line);
  }
  return gutter;
}

function toNodes(doc: Document, nodes: ElementContent[]): Node[] {
  return nodes.map((node) => {
    if (node.type === "text") return doc.createTextNode(node.value);
    if (node.type !== "element") return doc.createTextNode("");
    const span = doc.createElement("span");
    span.className = ((node.properties.className as string[] | undefined) ?? []).join(" ");
    span.append(...toNodes(doc, node.children));
    return span;
  });
}
