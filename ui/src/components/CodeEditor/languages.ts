// Lazy language loading + fieldtype → language mapping for CodeEditor.
//
// `loadLanguage` dynamically imports the matching `@codemirror/lang-*` package
// so each language tree-shakes into its own async chunk (apps that never render
// a code field pay nothing). `fieldtypeToLanguage` derives the key from a
// FormLayout field the way core Frappe derives an Ace mode from `field.options`.

import type { Extension } from "@codemirror/state";
import type { FieldMeta } from "../FormLayout/types";

/**
 * Dynamically import the CodeMirror language extension for `key`.
 * Returns `null` for plain text / unknown keys (no highlighting).
 */
export async function loadLanguage(key?: string): Promise<Extension | null> {
  switch (key) {
    case "json": {
      const { json } = await import("@codemirror/lang-json");
      return json();
    }
    case "html": {
      const { html } = await import("@codemirror/lang-html");
      return html();
    }
    case "javascript": {
      const { javascript } = await import("@codemirror/lang-javascript");
      return javascript();
    }
    case "python": {
      const { python } = await import("@codemirror/lang-python");
      return python();
    }
    case "sql": {
      const { sql } = await import("@codemirror/lang-sql");
      return sql();
    }
    case "markdown": {
      const { markdown } = await import("@codemirror/lang-markdown");
      return markdown();
    }
    case "css": {
      const { css } = await import("@codemirror/lang-css");
      return css();
    }
    case "scss": {
      // `lang-sass` covers both — `indented: false` selects SCSS (brace) syntax.
      const { sass } = await import("@codemirror/lang-sass");
      return sass({ indented: false });
    }
    case "yaml": {
      const { yaml } = await import("@codemirror/lang-yaml");
      return yaml();
    }
    case "xml": {
      const { xml } = await import("@codemirror/lang-xml");
      return xml();
    }
    default:
      return null;
  }
}

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
