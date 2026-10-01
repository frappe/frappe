// Finds each component tag and value name in a compiled template that its component does not list.
import { walk } from "./walk.mjs";

const ELEMENT = 1;
const SIMPLE_EXPRESSION = 4;
const COMPONENT_TAG = 1;
const DYNAMIC_COMPONENT = new Set(["component", "Component"]);
// With prefixIdentifiers, the compiler rewrites each free name in an expression to `_ctx.<name>`.
const CONTEXT_NAME = /^_ctx\.([\w$]+)$/;

const READERS = {
  name: stringValue,
  components: objectKeys,
  props: keysOrStrings,
  inject: keysOrStrings,
  computed: objectKeys,
  methods: objectKeys,
  data: returnedKeys,
  setup: returnedKeys,
  mixins: () => null,
  extends: () => null,
};
const COMPONENT_LISTS = new Set(["name", "components"]);

/** Each unknown name in `templateAst`, as `{ offset, message }` with the offset in the template text. */
export function checkNames(component, templateAst, names) {
  const known = knownNames(component, names);
  if (!known) return [];
  const errors = new Map();
  walk(templateAst, (node) => {
    if (isUnknownComponent(node, known.components)) {
      errors.set(node.loc.start.offset + 1, unknownComponent(node.tag));
    }
    const name =
      node.type === SIMPLE_EXPRESSION && CONTEXT_NAME.exec(node.content)?.[1];
    if (name && !name.startsWith("$") && !known.values.has(name)) {
      errors.set(node.loc.start.offset, unknownValue(name));
    }
  });
  return [...errors].map(([offset, message]) => ({ offset, message }));
}

/** The names the component lists, or null when one list is not written out in place. */
function knownNames(component, names) {
  const known = {
    components: new Set(names.components),
    values: new Set(names.values),
  };
  for (const property of component.properties) {
    if (property.type === "SpreadElement" || property.computed) return null;
    const key = keyName(property);
    if (!Object.hasOwn(READERS, key)) continue;
    const found = READERS[key](
      property.type === "ObjectMethod" ? property : property.value
    );
    if (!found) return null;
    const list = COMPONENT_LISTS.has(key) ? known.components : known.values;
    for (const name of found) list.add(name);
  }
  return known;
}

function isUnknownComponent(node, components) {
  if (node.type !== ELEMENT || node.tagType !== COMPONENT_TAG) return false;
  if (DYNAMIC_COMPONENT.has(node.tag)) return false;
  // Vue's own lookup order for a component tag.
  const camel = node.tag.replace(/-(\w)/g, (_, letter) => letter.toUpperCase());
  const pascal = camel.charAt(0).toUpperCase() + camel.slice(1);
  return ![node.tag, camel, pascal].some((name) => components.has(name));
}

function unknownComponent(tag) {
  return `<${tag}> is not a known component. Import it and list it in components:.`;
}

function unknownValue(name) {
  return `"${name}" is not a known name. Add it to props, setup(), data(), computed:, methods: or inject:.`;
}

function keyName(property) {
  if (property.key.type === "Identifier") return property.key.name;
  if (property.key.type === "StringLiteral") return property.key.value;
  return null;
}

function stringValue(node) {
  if (node.type === "StringLiteral") return [node.value];
  if (node.type === "TemplateLiteral" && !node.expressions.length) {
    return [node.quasis[0].value.cooked];
  }
  return null;
}

function objectKeys(node) {
  if (node.type !== "ObjectExpression") return null;
  const keys = [];
  for (const property of node.properties) {
    if (property.type === "SpreadElement" || property.computed) return null;
    const key = keyName(property);
    if (key === null) return null;
    keys.push(key);
  }
  return keys;
}

function keysOrStrings(node) {
  if (node.type !== "ArrayExpression") return objectKeys(node);
  const strings = node.elements.map((element) =>
    element?.type === "StringLiteral" ? element.value : null
  );
  return strings.includes(null) ? null : strings;
}

/** The keys of every object the function returns, or null when one return is not an object. */
function returnedKeys(fn) {
  if (!isFunction(fn)) return null;
  if (fn.body.type !== "BlockStatement") return objectKeys(fn.body);
  const keys = [];
  let readable = true;
  walk(fn.body, (node) => {
    if (isFunction(node)) return false;
    if (node.type !== "ReturnStatement" || !node.argument) return;
    const returned = objectKeys(node.argument);
    if (returned) keys.push(...returned);
    else readable = false;
  });
  return readable ? keys : null;
}

function isFunction(node) {
  return [
    "FunctionExpression",
    "ArrowFunctionExpression",
    "FunctionDeclaration",
    "ObjectMethod",
    "ClassMethod",
  ].includes(node.type);
}
