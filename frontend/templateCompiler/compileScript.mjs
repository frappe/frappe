// Turns each unquoted `template:` string in a script into a render function, on the same lines.
import { createHash } from "node:crypto";
import { readdirSync, readFileSync } from "node:fs";
import { createRequire } from "node:module";
import { checkNames } from "./checkNames.mjs";
import { walk } from "./walk.mjs";

const require = createRequire(import.meta.url);
const {
  babelParse,
  compileTemplate,
  MagicString,
} = require("vue/compiler-sfc");
const fromVue = createRequire(require.resolve("vue/package.json"));
// The production build: `@vue/compiler-dom` picks its build from the caller's NODE_ENV.
const compilerDom = fromVue("@vue/compiler-dom/dist/compiler-dom.cjs.prod.js");
const names = require("./names.json");

// hoistStatic must stay false: with true, the compiler runs template expressions through `new Function`.
const COMPILE_OPTIONS = {
  isProd: true,
  transformAssetUrls: false,
  compilerOptions: { hoistStatic: false, sourceMap: false },
};
// The word alone, so the shorthand `{ template }` and a commented key still reach the parse.
export const TEMPLATE_KEY = /\btemplate\b/;
const LINE_BREAK = /\r\n?|[\n\u2028\u2029]/g;

/**
 * Compiles every template in `source`, with a source map when given the file's name.
 * @returns {{ code: string | null, map?: object, errors: { line: number, column: number, message: string }[] }}
 */
export function compileScript(source, { filename } = {}) {
  if (!TEMPLATE_KEY.test(source)) return { code: source, errors: [] };
  const plugins = filename?.endsWith(".ts") ? ["typescript"] : [];
  let program;
  try {
    program = babelParse(source, { sourceType: "module", plugins }).program;
  } catch (error) {
    return { code: null, errors: [parseError(error)] };
  }
  const templates = findTemplates(source, program);
  if (!templates.length) return { code: source, errors: [] };

  const output = new MagicString(source);
  const helpers = new Map();
  const errors = [];
  for (const template of templates) {
    if (template.error) {
      errors.push(template.error);
      continue;
    }
    const render = compileOne(source, template, helpers, errors);
    if (render)
      output.overwrite(template.property.start, template.property.end, render);
  }
  if (!errors.length) errors.push(...helperClashes(source, program, helpers));
  if (errors.length) {
    errors.sort((a, b) => a.line - b.line || a.column - b.column);
    return { code: null, errors };
  }
  const imports = [...helpers].map(([name, local]) => `${name} as ${local}`);
  if (imports.length)
    output.prepend(`import { ${imports.join(", ")} } from "vue"; `);
  const code = output.toString();
  if (!filename) return { code, errors: [] };
  const map = output.generateMap({ source: filename, hires: true });
  return { code, map, errors: [] };
}

/** What the server's cache key holds besides the source hash. */
export function cacheKeyParts() {
  return {
    compiler: "@vue/compiler-dom",
    version: require("vue/package.json").version,
    build: "cjs.prod",
    options: { ...COMPILE_OPTIONS, names },
    scriptVersion: hashOwnFiles(),
  };
}

/** Each unquoted `template:` key outside a destructuring pattern, with its text or its error. */
function findTemplates(source, program) {
  const templates = [];
  walk(program, (node, parent) => {
    if (node.type !== "ObjectProperty" || node.computed) return;
    if (node.key.type !== "Identifier" || node.key.name !== "template") return;
    if (parent.type === "ObjectPattern") return;
    templates.push(readTemplate(source, node, parent));
  });
  return templates;
}

function readTemplate(source, property, component) {
  const value = property.value;
  const text =
    value.type === "StringLiteral"
      ? value.value
      : value.type === "TemplateLiteral" && !value.expressions.length
      ? value.quasis[0].value.cooked
      : null;
  if (property.shorthand || text === null) {
    const at = lineAndColumn(
      source,
      (property.shorthand ? property : value).start
    );
    const message =
      'template: must be a string, or a backtick string with no ${} parts. For data, quote the key: "template":.';
    return { property, error: { ...at, message } };
  }
  const contentStart = value.start + 1;
  const raw = source.slice(contentStart, value.end - 1);
  return { property, component, text, contentStart, offsets: rawOffsets(raw) };
}

/** The render method that replaces the template's property, or null after adding its errors. */
function compileOne(source, template, helpers, errors) {
  const result = compileTemplate({
    ...COMPILE_OPTIONS,
    compiler: compilerDom,
    source: template.text,
    filename: "template",
    id: "template",
  });
  const found = result.errors.length
    ? result.errors.map((error) => ({
        offset: error.loc?.start.offset,
        message: error.message ?? String(error),
      }))
    : checkNames(template.component, result.ast, names);
  for (const { offset, message } of found) {
    const at = template.contentStart + (template.offsets[offset] ?? 0);
    errors.push({ ...lineAndColumn(source, at), message });
  }
  if (found.length) return null;
  return renderMethod(result.code, template.property, helpers);
}

/** An error at each top-level name of the script that a compiled template also imports. */
function helperClashes(source, program, helpers) {
  const locals = new Set(helpers.values());
  const message = (name) =>
    `"${name}" is a name the compiled template needs. Rename it.`;
  return topLevelNames(program)
    .filter((identifier) => locals.has(identifier.name))
    .map((identifier) => ({
      ...lineAndColumn(source, identifier.start),
      message: message(identifier.name),
    }));
}

function topLevelNames(program) {
  const names = [];
  for (let statement of program.body) {
    if (statement.type.startsWith("Export") && statement.declaration) {
      statement = statement.declaration;
    }
    if (statement.type === "ImportDeclaration") {
      names.push(...statement.specifiers.map((specifier) => specifier.local));
    } else if (statement.type === "VariableDeclaration") {
      for (const declarator of statement.declarations) {
        walk(
          declarator.id,
          (node, parent) => {
            if (
              node.type === "Identifier" &&
              bindsName(parent, node, declarator)
            )
              names.push(node);
          },
          declarator
        );
      }
    } else if (statement.id) {
      names.push(statement.id);
    }
  }
  return names;
}

function bindsName(parent, identifier, declarator) {
  if (parent === declarator) return true;
  if (parent.type === "ObjectProperty") return parent.value === identifier;
  if (parent.type === "AssignmentPattern") return parent.left === identifier;
  return parent.type === "ArrayPattern" || parent.type === "RestElement";
}

function renderMethod(code, property, helpers) {
  const file = babelParse(code, { sourceType: "module", tokens: true });
  let render;
  for (const statement of file.program.body) {
    if (statement.type === "ImportDeclaration") {
      for (const specifier of statement.specifiers) {
        helpers.set(specifier.imported.name, specifier.local.name);
      }
    } else {
      render = statement.declaration;
    }
  }
  const params = code.slice(render.params[0].start, render.params.at(-1).end);
  const body = oneLine(code, render.body, file.tokens);
  const lineBreaks = property.loc.end.line - property.loc.start.line;
  return `render(${params}) {${body}${"\n".repeat(lineBreaks)}}`;
}

/** The function body on one line, with the semicolons that line breaks supplied before. */
function oneLine(code, body, tokens) {
  const statementEnds = new Set();
  walk(body, (node, parent) => {
    if (needsSemicolon(node, parent) && code[node.end - 1] !== ";") {
      statementEnds.add(node.end);
    }
  });
  let text = "";
  let previous = null;
  for (const token of tokens) {
    const isComment = typeof token.type === "string";
    if (isComment || token.start <= body.start || token.end >= body.end)
      continue;
    if (previous) {
      const gap = code.slice(previous.end, token.start);
      if (statementEnds.has(previous.end)) text += ";";
      text += /[\n\r\u2028\u2029]/.test(gap) ? " " : gap;
    }
    // A raw line break left in a string token would move every later line.
    text += code
      .slice(token.start, token.end)
      .replace(/(?<!\\)((?:\\\\)*)\\(\r\n?|[\n\u2028\u2029])/g, "$1")
      .replace(/\r\n?|\n/g, "\\n")
      .replace(/\u2028/g, "\\u2028")
      .replace(/\u2029/g, "\\u2029");
    previous = token;
  }
  return text;
}

function needsSemicolon(node, parent) {
  if (node.type === "VariableDeclaration") return !/^For/.test(parent?.type);
  return [
    "ExpressionStatement",
    "ReturnStatement",
    "ThrowStatement",
    "BreakStatement",
    "ContinueStatement",
    "DebuggerStatement",
    "DoWhileStatement",
  ].includes(node.type);
}

/** For each character of the cooked string, its offset in the raw text between the quotes. */
function rawOffsets(raw) {
  const offsets = [];
  let index = 0;
  while (index < raw.length) {
    const start = index;
    const [length, produced] = rawStep(raw, index);
    index += length;
    for (let i = 0; i < produced; i++) offsets.push(start);
  }
  offsets.push(raw.length);
  return offsets;
}

/** How many raw characters the next cooked step reads, and how many characters it produces. */
function rawStep(raw, index) {
  if (raw.startsWith("\r\n", index)) return [2, 1];
  if (raw[index] !== "\\") return [1, 1];
  const next = raw[index + 1];
  if (raw.startsWith("\r\n", index + 1)) return [3, 0];
  if ("\n\r\u2028\u2029".includes(next)) return [2, 0];
  if (next === "x") return [4, 1];
  if (next !== "u") return [2, 1];
  if (raw[index + 2] !== "{") return [6, 1];
  const close = raw.indexOf("}", index);
  const codePoint = parseInt(raw.slice(index + 3, close), 16);
  return [close + 1 - index, codePoint > 0xffff ? 2 : 1];
}

function lineAndColumn(source, offset) {
  let line = 1;
  let lineStart = 0;
  for (const lineBreak of source.slice(0, offset).matchAll(LINE_BREAK)) {
    line++;
    lineStart = lineBreak.index + lineBreak[0].length;
  }
  return { line, column: offset - lineStart + 1 };
}

function parseError(error) {
  const message = error.message.replace(/\s*\(\d+:\d+\)$/, "");
  if (!error.loc) return { line: 1, column: 1, message };
  return { line: error.loc.line, column: error.loc.column + 1, message };
}

function hashOwnFiles() {
  const folder = new URL(".", import.meta.url);
  const hash = createHash("sha256");
  const entries = readdirSync(folder, { withFileTypes: true });
  for (const file of entries
    .filter((entry) => entry.isFile())
    .map((entry) => entry.name)
    .sort()) {
    hash.update(readFileSync(new URL(file, folder)));
  }
  return hash.digest("hex").slice(0, 16);
}
