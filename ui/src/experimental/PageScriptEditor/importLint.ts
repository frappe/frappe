// The one import rule, enforced rather than announced (wayfinder ticket 23): a
// Page Script is evaluated as a real ES module through a blob URL, so its bare
// specifiers resolve through the page's import map and nothing else does — not a
// relative path (there is no file to be relative to), not an unlisted package,
// and not a subpath of a listed one.
//
// This is a text scan, not a parse. frappe-ui's `CodeEditor` exposes no way to
// add a CodeMirror lint source or completion source — no `extensions` prop, no
// `defineExpose` of the view — so the report is an `Alert` beside the editor
// rather than a squiggle under the specifier. See ticket 26's resolution.

/**
 * The bare specifiers the host's import map publishes.
 *
 * Kept in step by hand with `vite/extensionHost.js`, which builds the map and is
 * the source of truth. Bare roots only: the map has no trailing-slash entries,
 * so `frappe-ui/code-editor` and `@framework/ui/experimental` do not resolve —
 * the experimental barrel is folded into the bare specifier for that reason.
 */
export const SHARED_DEPS = [
  "vue",
  "vue-router",
  "frappe-ui",
  "@framework/ui",
] as const;

// Matched against source whose comments and string *contents* have been blanked,
// so only real code can match and only a real string literal can be the
// specifier. Group 2 is the specifier — read back from the original text by
// index, since in the blanked text it is spaces.
const IMPORT_FORMS = [
  /\bimport\s+[^;()]*?\bfrom\s*(['"])([^'"]*)\1/dg,
  /\bexport\s+[^;()]*?\bfrom\s*(['"])([^'"]*)\1/dg,
  /\bimport\s*\(\s*(['"])([^'"]*)\1\s*\)/dg,
  /\bimport\s*(['"])([^'"]*)\1/dg,
];

/**
 * The specifiers in `source` that will not resolve at runtime, in the order they
 * appear, without duplicates. An empty array means the script's imports are fine
 * — it says nothing about whether the rest of it parses.
 */
export function unresolvableImports(source: string): string[] {
  const code = blankNonCode(source);
  const found = new Map<number, string>();
  for (const pattern of IMPORT_FORMS) {
    for (const match of code.matchAll(pattern)) {
      const at = match.indices?.[2];
      if (!at) continue;
      const specifier = source.slice(at[0], at[1]);
      if (!resolves(specifier)) found.set(at[0], specifier);
    }
  }
  return [...new Set([...found].sort(byPosition).map(([, name]) => name))];
}

function resolves(specifier: string) {
  return (SHARED_DEPS as readonly string[]).includes(specifier);
}

function byPosition(one: [number, string], other: [number, string]) {
  return one[0] - other[0];
}

/**
 * `source` with its comments and its string literals' contents replaced by
 * spaces, quotes and newlines kept. Same length as the input, so a match's
 * offsets still point at the original text.
 *
 * Blanking string contents is what keeps `const help = 'import x from "dayjs"'`
 * from being read as an import: an undismissible Alert has to be right.
 */
function blankNonCode(source: string) {
  let out = "";
  let index = 0;
  while (index < source.length) {
    const char = source[index];
    if (char === "/" && source[index + 1] === "/") {
      const end = indexOrEnd(source, "\n", index);
      out += blank(source.slice(index, end));
      index = end;
    } else if (char === "/" && source[index + 1] === "*") {
      const end = Math.min(
        indexOrEnd(source, "*/", index + 2) + 2,
        source.length,
      );
      out += blank(source.slice(index, end));
      index = end;
    } else if (char === '"' || char === "'" || char === "`") {
      const end = endOfString(source, index);
      // Quotes kept so the specifier patterns can still see a string was here.
      const closed = end > index + 1 && source[end - 1] === char;
      out +=
        char +
        blank(source.slice(index + 1, closed ? end - 1 : end)) +
        (closed ? char : "");
      index = end;
    } else {
      out += char;
      index += 1;
    }
  }
  return out;
}

/** Where the string literal opened at `start` ends, past the closing quote. */
function endOfString(source: string, start: number) {
  const quote = source[start];
  let index = start + 1;
  while (index < source.length) {
    if (source[index] === "\\") index += 2;
    else if (source[index] === quote) return index + 1;
    // An unterminated quote is a string the author is still typing; stopping at
    // the newline keeps the rest of the script scannable.
    else if (source[index] === "\n" && quote !== "`") return index;
    else index += 1;
  }
  return source.length;
}

/** Same length, same line breaks, no content. */
function blank(text: string) {
  return text.replace(/[^\n]/g, " ");
}

function indexOrEnd(source: string, needle: string, from: number) {
  const at = source.indexOf(needle, from);
  return at === -1 ? source.length : at;
}
