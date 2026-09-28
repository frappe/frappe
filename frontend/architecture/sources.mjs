// Reads the desk source files from a frappe checkout: their line counts, imports and API method strings.

import fs from "node:fs";
import path from "node:path";
import { execSync } from "node:child_process";

const JS_EXT = [".ts", ".vue", ".js", ".mjs"];
const SKIPPED_DIRS = ["node_modules", "tests", "stories", "__pycache__"];
const IMPORT_PATTERNS = [
  /\b(import|export)\s+(type\s+)?[^'";]*?\bfrom\s*['"]([^'"\n]+)['"]/g,
  /\bimport\s*['"]([^'"\n]+)['"]/g,
  /\bimport\s*\(\s*['"]([^'"\n]+)['"]\s*\)/g,
];

export class Sources {
  constructor(root) {
    this.root = path.resolve(root);
    this.uiExports = null;
  }

  // frontend/src and frontend/plugin, plus the ui/src files they reach through imports.
  jsFiles() {
    this.uiExports = this.readUiExports();
    const files = new Map();
    const queue = [
      ...this.walk("frontend/src"),
      ...this.walk("frontend/plugin"),
    ].filter(isCountedJs);
    while (queue.length) {
      const file = queue.pop();
      if (files.has(file)) continue;
      const info = this.readJsFile(file);
      files.set(file, info);
      for (const imp of info.imports) {
        if (imp.target && !files.has(imp.target) && isCountedJs(imp.target))
          queue.push(imp.target);
      }
      // An import of a test helper or a declaration file is not an edge.
      info.imports = info.imports.filter(
        (imp) => !imp.target || isCountedJs(imp.target)
      );
    }
    return files;
  }

  pyFiles() {
    const files = new Map();
    for (const file of this.walk("frappe/shell").filter(isCountedPy)) {
      const text = this.read(file);
      files.set(file, {
        lines: countLines(text),
        imports: this.parsePyImports(file, text),
      });
    }
    return files;
  }

  resolvePythonMethod(dotted) {
    const parts = dotted.split(".");
    for (let i = parts.length; i > 1; i--) {
      const target = this.pyFile(parts.slice(0, i).join("/"));
      if (target) return target;
    }
    return null;
  }

  // Python outside frappe/shell that names a frappe.shell module: imports and hooks.py strings.
  shellCallers() {
    const refs = [];
    for (const line of this.grepShellReferences()) {
      const [file] = line.split(":");
      if (!isCountedPy(file)) continue;
      const kind = file === "frappe/hooks.py" ? "hook" : "import";
      for (const m of line.matchAll(/frappe\.shell\.([a-z_]+)/g)) {
        const to = this.pyFile(`frappe/shell/${m[1]}`);
        if (to) refs.push({ from: file, to, kind });
      }
    }
    return refs;
  }

  lineCount(file) {
    if (!fs.existsSync(path.join(this.root, file))) return null;
    return countLines(this.read(file));
  }

  // ---------- JS ----------

  readJsFile(file) {
    const text = this.read(file);
    const code = stripComments(text);
    return {
      lines: countLines(text),
      imports: this.parseJsImports(file, code),
      apiCalls: parseApiCalls(code),
    };
  }

  parseJsImports(file, code) {
    const found = [];
    for (const [index, re] of IMPORT_PATTERNS.entries()) {
      for (const m of code.matchAll(re)) {
        const spec = index === 0 ? m[3] : m[1];
        found.push({
          spec,
          typeOnly: index === 0 && Boolean(m[2]),
          dynamic: index === 2,
        });
      }
    }
    return found.map((imp) => this.resolveImport(file, imp));
  }

  resolveImport(file, { spec, typeOnly, dynamic }) {
    const clean = spec.split("?")[0];
    if (clean.startsWith("virtual:frappe/")) {
      return {
        kind: "virtual",
        target: "frontend/plugin/contributions.js",
        typeOnly,
        dynamic,
      };
    }
    const resolved = this.resolveJs(file, clean);
    if (resolved)
      return { kind: "import", target: resolved, typeOnly, dynamic };
    const pkg = packageName(clean);
    return pkg
      ? { kind: "import", external: pkg, typeOnly, dynamic }
      : { kind: "import" };
  }

  resolveJs(fromFile, spec) {
    const base = this.importBase(fromFile, spec);
    if (!base) return null;
    return this.firstExisting([
      base,
      ...JS_EXT.map((e) => base + e),
      ...JS_EXT.map((e) => path.join(base, "index" + e)),
    ]);
  }

  importBase(fromFile, spec) {
    if (spec.startsWith(".")) return path.join(path.dirname(fromFile), spec);
    if (spec.startsWith("@/")) return path.join("frontend/src", spec.slice(2));
    if (spec === "@shell") return "frontend/src/public.ts";
    if (spec === "@framework/ui" || spec.startsWith("@framework/ui/")) {
      const sub = "." + spec.slice("@framework/ui".length);
      const fallback =
        sub === "." ? "src/index.ts" : path.join("src", sub.slice(2));
      return path.join("ui", this.uiExports[sub] || fallback);
    }
    return null;
  }

  readUiExports() {
    const pkg = JSON.parse(this.read("ui/package.json"));
    const map = {};
    for (const [key, value] of Object.entries(pkg.exports || {})) {
      if (key.includes("*")) continue;
      map[key] = (typeof value === "string" ? value : value.import).replace(
        /^\.\//,
        ""
      );
    }
    return map;
  }

  // ---------- Python ----------

  parsePyImports(file, text) {
    const targets = [];
    for (const m of text.matchAll(
      /^\s*from\s+(\.+)([\w.]*)\s+import\s+([\w, ()]+)/gm
    )) {
      const target = this.relativePyImport(file, m[1], m[2]);
      if (target && target !== file) targets.push(target);
    }
    const absolute = [
      /^\s*from\s+(frappe(?:\.\w+)+)\s+import\s+/gm,
      /^\s*import\s+(frappe(?:\.\w+)+)/gm,
    ];
    for (const re of absolute) {
      for (const m of text.matchAll(re)) {
        const target = this.pyFile(m[1].replace(/\./g, "/"));
        if (target) targets.push(target);
      }
    }
    return targets;
  }

  relativePyImport(file, dots, module) {
    const up = dots.length - 1;
    const dir = path.join(path.dirname(file), ...Array(up).fill(".."));
    if (!module) return this.pyFile(path.join(dir, "__init__"));
    return this.pyFile(path.join(dir, ...module.split(".")));
  }

  pyFile(modPath) {
    return this.firstExisting([
      modPath + ".py",
      path.join(modPath, "__init__.py"),
    ]);
  }

  grepShellReferences() {
    try {
      const cmd = `git grep -n -E "frappe\\.shell\\.[a-z_]+" -- "frappe/*.py" ":!frappe/shell/*"`;
      const out = execSync(cmd, { cwd: this.root, encoding: "utf8" });
      return out.split("\n").filter(Boolean);
    } catch {
      // git grep exits non-zero when nothing matches.
      return [];
    }
  }

  // ---------- files ----------

  walk(dir) {
    const abs = path.join(this.root, dir);
    if (!fs.existsSync(abs)) return [];
    const out = [];
    for (const entry of fs.readdirSync(abs, { withFileTypes: true })) {
      const rel = path.join(dir, entry.name);
      if (!entry.isDirectory()) out.push(rel);
      else if (!SKIPPED_DIRS.includes(entry.name)) out.push(...this.walk(rel));
    }
    return out;
  }

  firstExisting(candidates) {
    for (const c of candidates) {
      const abs = path.join(this.root, c);
      if (fs.existsSync(abs) && fs.statSync(abs).isFile())
        return path.normalize(c);
    }
    return null;
  }

  read(file) {
    return fs.readFileSync(path.join(this.root, file), "utf8");
  }
}

// Tests, stories and type declaration files are left out of nodes and counts.
function isCountedJs(file) {
  if (!JS_EXT.some((e) => file.endsWith(e)) || file.endsWith(".d.ts"))
    return false;
  return (
    !/(^|\/)(tests|stories|node_modules)\//.test(file) &&
    !/\.(test|spec|stories)\./.test(file)
  );
}

function isCountedPy(file) {
  return (
    file.endsWith(".py") &&
    !/(^|\/)tests?\//.test(file) &&
    !/(^|\/)test_[^/]*\.py$/.test(file)
  );
}

function parseApiCalls(code) {
  return [...code.matchAll(/['"`](frappe(?:\.[a-z0-9_]+){2,})['"`]/g)].map(
    (m) => m[1]
  );
}

function packageName(spec) {
  if (/\s/.test(spec) || spec.startsWith("/")) return null;
  if (spec.startsWith("~icons/")) return "~icons";
  if (spec.startsWith("node:")) return spec;
  const parts = spec.split("/");
  return spec.startsWith("@") ? parts.slice(0, 2).join("/") : parts[0];
}

function stripComments(text) {
  return text
    .replace(/\/\*[\s\S]*?\*\//g, "")
    .replace(/(^|[^:"'`\\])\/\/.*$/gm, "$1");
}

function countLines(text) {
  if (!text) return 0;
  return text.split("\n").length - (text.endsWith("\n") ? 1 : 0);
}
