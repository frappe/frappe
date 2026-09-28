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
