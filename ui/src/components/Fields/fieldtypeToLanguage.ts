// Maps a Frappe FormLayout fieldtype to a CodeMirror language key for the
// CodeEditor primitive (now published from `frappe-ui/code-editor`). This is
// FormLayout-specific glue — it understands Frappe fieldtypes and the Ace mode
// stored in `field.options` — so it lives here with the field wrapper rather than
// in the framework-agnostic editor primitive.

import type { FieldMeta } from "./types";

/**
 * Map a FormLayout field to a CodeMirror language key.
 *   JSON → json, Markdown Editor → markdown, HTML Editor → html.
 *   Code → normalize `field.options` (core stores the Ace mode there).
 */
export function fieldtypeToLanguage(field: FieldMeta): string {
  switch (field.fieldtype) {
    case "JSON":
      return "json";
    case "Markdown Editor":
      return "markdown";
    case "HTML Editor":
      return "html";
    case "Code":
      return normalizeCodeOption(field.options);
    default:
      return "plain";
  }
}

// Each canonical language key lists the aliases a `Code` field's `options` might
// carry — short forms (`js`, `py`), file extensions (`mjs`, `yml`), and common
// names (`node`, `postgresql`). `field.options` is matched case-insensitively.
const CODE_OPTION_ALIASES: Record<string, string[]> = {
  javascript: [
    "javascript",
    "js",
    "jsx",
    "mjs",
    "cjs",
    "node",
    "ecmascript",
    "typescript",
    "ts",
  ],
  python: ["python", "py", "python3"],
  html: ["html", "htm", "xhtml"],
  css: ["css"],
  scss: ["scss", "sass"],
  sql: ["sql", "mysql", "mariadb", "postgres", "postgresql", "pgsql", "sqlite"],
  yaml: ["yaml", "yml"],
  xml: ["xml", "rss", "svg", "xsl", "xsd"],
  json: ["json", "jsonc", "json5"],
  markdown: ["markdown", "md", "mkd", "mdown"],
  // Jinja templates are HTML-ish — highlight as HTML.
  html_template: ["jinja", "jinja2", "j2", "twig"],
};

// alias → canonical key (built once). `html_template` resolves to `html`.
const ALIAS_TO_LANGUAGE: Record<string, string> = (() => {
  const map: Record<string, string> = {};
  for (const [key, aliases] of Object.entries(CODE_OPTION_ALIASES)) {
    const lang = key === "html_template" ? "html" : key;
    for (const alias of aliases) map[alias] = lang;
  }
  return map;
})();

function normalizeCodeOption(option?: string): string {
  return ALIAS_TO_LANGUAGE[(option ?? "").trim().toLowerCase()] ?? "plain";
}
