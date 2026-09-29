// Text rules for the source files: which files count, and how lines, comments and names are read.

export const JS_EXT = [".ts", ".vue", ".js", ".mjs"];

export function lineAt(text, index) {
  return text.slice(0, index).split("\n").length;
}

// Tests, stories and type declaration files are left out of nodes and counts.
export function isCountedJs(file) {
  if (!JS_EXT.some((e) => file.endsWith(e)) || file.endsWith(".d.ts"))
    return false;
  return (
    !/(^|\/)(tests|stories|node_modules)\//.test(file) &&
    !/\.(test|spec|stories)\./.test(file)
  );
}

export function isCountedPy(file) {
  return (
    file.endsWith(".py") &&
    !/(^|\/)tests?\//.test(file) &&
    !/(^|\/)test_[^/]*\.py$/.test(file)
  );
}

export function parseApiCalls(code) {
  return [...code.matchAll(/['"`](frappe(?:\.[a-z0-9_]+){2,})['"`]/g)].map(
    (m) => ({
      method: m[1],
      line: lineAt(code, m.index),
    })
  );
}

// The names an `import ... from` or `export ... from` statement takes from its module, each
// as { from, as }. A default import is named "default"; `* from` sets star; `* as x` names nothing.
export function importedNames(statement) {
  const clause = statement
    .replace(/^(import|export)\s+(type\s+)?/, "")
    .replace(/\bfrom\s*['"][^'"]*['"]$/, "")
    .trim();
  const braces = clause.match(/\{([^}]*)\}/);
  const names = braces ? braces[1].split(",").flatMap(namePair) : [];
  const outside = clause.replace(/\{[^}]*\}/, "").split(",");
  for (const part of outside.map((p) => p.trim()).filter(Boolean)) {
    if (!part.startsWith("*")) names.push({ from: "default", as: "default" });
  }
  return { names, star: clause === "*" };
}

// The names a file defines and exports itself, without `from`.
export function localExports(code) {
  const names = new Set();
  const declared =
    /\bexport\s+(?:declare\s+)?(?:default\s+)?(?:async\s+)?(?:abstract\s+)?(?:function\*?|class|const|let|var|type|interface|enum)\s+([\w$]+)/g;
  for (const m of code.matchAll(declared)) names.add(m[1]);
  for (const m of code.matchAll(
    /\bexport\s+(?:type\s+)?\{([^}]*)\}(?!\s*from)/g
  ))
    for (const { as } of m[1].split(",").flatMap(namePair)) names.add(as);
  if (/\bexport\s+default\b/.test(code)) names.add("default");
  return names;
}

function namePair(part) {
  const [from, as] = part
    .trim()
    .replace(/^type\s+/, "")
    .split(/\s+as\s+/);
  return from ? [{ from, as: as || from }] : [];
}

export function packageName(spec) {
  if (/\s/.test(spec) || spec.startsWith("/")) return null;
  if (spec.startsWith("~icons/")) return "~icons";
  if (spec.startsWith("node:")) return spec;
  const parts = spec.split("/");
  return spec.startsWith("@") ? parts.slice(0, 2).join("/") : parts[0];
}

export function stripComments(text) {
  return text
    .replace(/\/\*[\s\S]*?\*\//g, (m) => m.replace(/[^\n]/g, ""))
    .replace(/(^|[^:"'`\\])\/\/.*$/gm, "$1");
}

export function countLines(text) {
  if (!text) return 0;
  return text.split("\n").length - (text.endsWith("\n") ? 1 : 0);
}
