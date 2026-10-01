// JavaScript with Vue colors inside each `template:` string, by the same rule the compiler uses.
import {
  autocompletion,
  type CompletionContext,
  type CompletionResult,
} from "@codemirror/autocomplete";
import { javascriptLanguage } from "@codemirror/lang-javascript";
import { vueLanguage } from "@codemirror/lang-vue";
import { LanguageSupport, syntaxTree } from "@codemirror/language";
import { parseMixed, type SyntaxNode, type SyntaxNodeRef } from "@lezer/common";

const BUILT_IN_COMPONENTS = ["KeepAlive", "Suspense", "Teleport", "Transition", "TransitionGroup"];
const DIRECTIVES = [
  "v-if",
  "v-else-if",
  "v-else",
  "v-for",
  "v-show",
  "v-model",
  "v-bind",
  "v-on",
  "v-slot",
  "v-html",
  "v-text",
  "v-once",
  "v-pre",
  "v-memo",
  "v-cloak",
];
const NAME = /^[\w-]*$/;
const SELF_ESCAPE = /^\\["'\\`\r\n\u2028\u2029]$/;

type Read = (from: number, to: number) => string;

/** The JavaScript language, with Vue nested and completed in `template:` strings. */
export function templateLanguage(names: readonly string[] | null): LanguageSupport {
  const language = javascriptLanguage.configure({
    wrap: parseMixed((ref, input) => nestVue(ref, (from, to) => input.read(from, to))),
  });
  // lang-vue re-parses a `v-` attribute into a tree with no language data, so this is an override.
  const completion = autocompletion({
    override: [(context) => completeTemplate(context, names ?? BUILT_IN_COMPONENTS)],
  });
  return new LanguageSupport(language, completion);
}

function nestVue(ref: SyntaxNodeRef, read: Read) {
  if (!isTemplateValue(ref.node, read)) return null;
  const overlay = decodedRanges(ref.node, read);
  return overlay.length ? { parser: vueLanguage.parser, overlay } : null;
}

function completeTemplate(
  context: CompletionContext,
  names: readonly string[]
): CompletionResult | null {
  const { state, pos } = context;
  const read: Read = (from, to) => state.sliceDoc(from, to);
  const node = syntaxTree(state).resolveInner(pos, -1);
  const template = templateAround(node, read);
  if (!template) return null;
  const tagFrom = tagStart(node, pos);
  if (tagFrom !== null) {
    return offer(tagFrom, [...new Set([...scriptComponents(template, read), ...names])], "type");
  }
  const attributeFrom = attributeStart(node, pos);
  return attributeFrom === null ? null : offer(attributeFrom, DIRECTIVES, "keyword");
}

function offer(from: number, labels: readonly string[], type: string): CompletionResult {
  return { from, options: labels.map((label) => ({ label, type })), validFor: NAME };
}

function templateAround(node: SyntaxNode, read: Read) {
  let value: SyntaxNode | null = node;
  while (value && !isTemplateValue(value, read)) value = value.parent;
  return value;
}

function tagStart(node: SyntaxNode, pos: number) {
  if (node.name === "TagName") {
    const tag = node.parent?.name;
    return tag === "OpenTag" || tag === "SelfClosingTag" ? node.from : null;
  }
  return node.name === "StartTag" || node.name === "IncompleteTag" ? pos : null;
}

function attributeStart(node: SyntaxNode, pos: number) {
  if (node.name === "AttributeName" || node.name === "VueAttributeName") return node.from;
  return node.name === "OpenTag" || node.name === "SelfClosingTag" ? pos : null;
}

/** The keys of the `components:` object beside the template's own `template:` key. */
function scriptComponents(template: SyntaxNode, read: Read): string[] {
  const list = template.parent?.parent
    ?.getChildren("Property")
    .find((property) => keyOf(property, read) === "components")?.lastChild;
  if (list?.name !== "ObjectExpression") return [];
  return list.getChildren("Property").flatMap((property) => keyOf(property, read) ?? []);
}

function isTemplateValue(node: SyntaxNode, read: Read) {
  if (node.name === "TemplateString") {
    if (node.getChild("Interpolation")) return false;
  } else if (node.name !== "String") {
    return false;
  }
  const key = node.parent?.name === "Property" ? node.parent.firstChild : null;
  return key?.name === "PropertyDefinition" && read(key.from, key.to) === "template";
}

/** The string's inside, less the backslash of each escape that decodes to the next character. */
function decodedRanges(string: SyntaxNode, read: Read) {
  const ranges: { from: number; to: number }[] = [];
  let from = string.from + 1;
  for (const escape of string.getChildren("Escape")) {
    if (!SELF_ESCAPE.test(read(escape.from, escape.to))) continue;
    if (from < escape.from) ranges.push({ from, to: escape.from });
    from = escape.from + 1;
  }
  if (from < string.to - 1) ranges.push({ from, to: string.to - 1 });
  return ranges;
}

function keyOf(property: SyntaxNode, read: Read) {
  const key = property.firstChild;
  if (key?.name === "PropertyDefinition") return read(key.from, key.to);
  if (key?.name === "String") return read(key.from + 1, key.to - 1);
  return null;
}
