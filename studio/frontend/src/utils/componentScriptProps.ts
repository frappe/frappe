import { typescriptLanguage } from "@codemirror/lang-javascript"
import type { SyntaxNode, Tree } from "@lezer/common"

import type { StudioComponentInput } from "@/runtime/types/Studio/StudioComponent"

// The props of a component are in its script. The editor's form reads and writes the `props`
// object of the script's default export as text. A save changes only the keys of a prop whose
// field the user changed, so all other code stays as written.

interface ScriptProps {
	/** Why the form cannot change the props. Empty when it can. */
	readOnlyReason: string
	exportObject?: SyntaxNode
	propsObject?: SyntaxNode
	entries: Map<string, SyntaxNode>
}

const NO_SCRIPT = "export default {}\n"
// the keys of a prop that the form writes, in the order of a new prop
const PROP_KEYS = ["type", "required", "default", "meta"] as const
type PropParts = Record<(typeof PROP_KEYS)[number], string | null>

const VUE_TYPE = "(?:String|Number|Boolean|Array|Object|Date|Function|Symbol|Error)"
// `String`, `[String, Number]`, `null`, each also with a TypeScript cast
const PLAIN_TYPE = new RegExp(
	`^(?:null|undefined|${VUE_TYPE}|\\[\\s*${VUE_TYPE}(?:\\s*,\\s*${VUE_TYPE})*\\s*,?\\s*\\])(?:\\s+as\\s[\\s\\S]+)?$`,
)

/** Whether the form can change the props of this script. If not, the reason to show. */
export function getPropsReadOnlyReason(source: string): string {
	return findScriptProps(source || NO_SCRIPT).readOnlyReason
}

/**
 * Whether the form can change this prop. It cannot change one that is a variable or a call,
 * or an object with a spread or a computed key, because those can set a key that the form removes.
 */
export function getPropReadOnlyReason(source: string, name: string): string {
	const entry = findScriptProps(source || NO_SCRIPT).entries.get(name)
	const value = getPropertyValue(entry)
	const isKnown =
		value?.name === "ObjectExpression"
			? value.getChildren("Property").length === getProperties(source, value).size
			: value && PLAIN_TYPE.test(getText(source, value))
	return !entry || isKnown ? "" : `"${name}" uses advanced prop options. Change it in the script.`
}

/**
 * Add, change or remove one prop, and return the new script.
 * `previous` is the prop to replace, and `prop` is its new definition. Pass only `prop` to
 * add a prop, and only `previous` to remove one.
 */
export function setScriptProp(
	source: string,
	previous: StudioComponentInput | null,
	prop: StudioComponentInput | null,
): string {
	source = source.trim() ? source : NO_SCRIPT
	const props = findScriptProps(source)
	if (props.readOnlyReason) throw new Error(props.readOnlyReason)

	const entry = previous && props.entries.get(previous.input_name)
	if (prop && prop.input_name !== previous?.input_name && props.entries.has(prop.input_name)) {
		throw new Error(`A prop named "${prop.input_name}" already exists.`)
	}

	let script = source
	if (prop && entry) {
		const text = `${getKeySource(prop.input_name)}: ${getChangedValue(source, entry, previous, prop)}`
		script = replaceRange(source, entry.from, entry.to, text)
	} else if (prop) {
		script = addProp(source, props, `${getKeySource(prop.input_name)}: ${getValueSource(getPropParts(prop))}`)
	} else if (entry) {
		script = removeProperty(source, entry)
	}
	if (hasSyntaxError(parse(script))) throw new Error("The default value is not valid JavaScript.")
	return script
}

/** The value of a changed prop: its text in the script, with only the changed keys set again. */
function getChangedValue(
	source: string,
	entry: SyntaxNode,
	previous: StudioComponentInput,
	prop: StudioComponentInput,
): string {
	const readOnlyReason = getPropReadOnlyReason(source, previous.input_name)
	if (readOnlyReason) throw new Error(readOnlyReason)
	const before = getPropParts(previous, false)
	const after = getPropParts(prop)
	const value = getPropertyValue(entry)!
	let text = getText(source, value)
	if (value.name !== "ObjectExpression") {
		// `title: String` is only a type
		const type = /^(null|undefined)$/.test(text) ? null : text
		return getValueSource({ ...after, type: before.type === after.type ? type : after.type })
	}
	// a default that the form does not show, such as a factory, does not fit a new type
	const isTypeChanged = before.type !== after.type
	for (const key of PROP_KEYS) {
		const isChanged = before[key] !== after[key] || (key === "default" && isTypeChanged)
		if (isChanged) text = setKey(text, key, after[key])
	}
	return text
}

/** The parts of a prop as the form gives them. Null for a key that the prop does not need. */
function getPropParts(prop: StudioComponentInput, isChecked = true): PropParts {
	const propType = prop.prop_type || "Any"
	const meta = []
	if (prop.control) meta.push(`control: "${prop.control}"`)
	if (prop.type === "select") meta.push(`options: ${JSON.stringify(getOptions(prop))}`)
	if (prop.description) meta.push(`description: ${JSON.stringify(prop.description)}`)
	return {
		type: propType === "Any" ? null : propType,
		required: prop.required ? "true" : null,
		default: getDefaultLiteral(prop, isChecked) ?? null,
		meta: meta.length ? `{ ${meta.join(", ")} }` : null,
	}
}

/** The value of a prop: `String`, `{ type: String, default: "md" }`, or `null` for no parts. */
function getValueSource(parts: PropParts): string {
	const keys = PROP_KEYS.filter((key) => parts[key] !== null)
	if (keys.length === 1 && parts.type) return parts.type
	return keys.length ? `{ ${keys.map((key) => `${key}: ${parts[key]}`).join(", ")} }` : "null"
}

function getDefaultLiteral(prop: StudioComponentInput, isChecked: boolean): string | undefined {
	const value = prop.default
	if (value === undefined || value === null || value === "") return undefined
	if (prop.type === "number") {
		if (isChecked && !Number.isFinite(Number(value))) throw new Error("The default value must be a number.")
		return String(Number(value))
	}
	// Vue gives a Boolean prop without a default the value false
	if (prop.type === "checkbox") return ["true", "1"].includes(String(value)) ? "true" : undefined
	if (isChecked && prop.type === "select" && !getOptions(prop).includes(String(value))) {
		throw new Error("The default value must be one of the options.")
	}
	// Vue calls a factory for each instance, so two instances do not share one object
	if (prop.type === "code") return `() => (${value})`
	return JSON.stringify(value)
}

function getOptions(prop: StudioComponentInput): string[] {
	return (prop.options || "").split("\n").filter((option) => option.trim())
}

function getKeySource(name: string): string {
	return /^[A-Za-z_$][\w$]*$/.test(name) ? name : JSON.stringify(name)
}

/** Set, add or remove one key of an object literal, given as text. A null value removes the key. */
function setKey(objectText: string, key: string, value: string | null): string {
	const source = `(${objectText})`
	const object = findObject(parse(source))!
	const property = getProperties(source, object).get(key)
	const text = `${key}: ${value}`
	let result = source
	if (property && value !== null) result = replaceRange(source, property.from, property.to, text)
	else if (property) result = removeProperty(source, property)
	else if (value !== null) result = addProperty(source, object, text)
	return result.slice(1, -1)
}

function findScriptProps(source: string): ScriptProps {
	const none = (readOnlyReason: string): ScriptProps => ({ readOnlyReason, entries: new Map() })
	const tree = parse(source)
	if (hasSyntaxError(tree)) return none("Fix the syntax error in the script first.")

	const exportObject = tree.topNode
		.getChildren("ExportDeclaration")
		.find((node) => node.getChild("default"))
		?.getChild("ObjectExpression")
	if (!exportObject) return none("The script must export an object as its default export.")

	const propsEntry = getProperties(source, exportObject).get("props")
	if (!propsEntry) return { readOnlyReason: "", exportObject, entries: new Map() }
	const propsObject = getPropertyValue(propsEntry)
	if (propsObject?.name !== "ObjectExpression") {
		return none("The script does not write its props as an object. Change them in the script.")
	}
	if (propsObject.getChildren("Property").some((property) => property.getChild("Spread"))) {
		return none("The script takes some props from another object. Change them in the script.")
	}
	return { readOnlyReason: "", exportObject, propsObject, entries: getProperties(source, propsObject) }
}

function getProperties(source: string, object: SyntaxNode): Map<string, SyntaxNode> {
	const properties = new Map<string, SyntaxNode>()
	for (const property of object.getChildren("Property")) {
		const key = property.firstChild
		if (key?.name === "PropertyDefinition") properties.set(getText(source, key), property)
		else if (key?.name === "String") properties.set(source.slice(key.from + 1, key.to - 1), property)
	}
	return properties
}

/** The value of `name: value`. A shorthand or a method has none. */
function getPropertyValue(property: SyntaxNode | undefined | null): SyntaxNode | null {
	return property?.getChild(":")?.nextSibling ?? null
}

function getText(source: string, node: SyntaxNode): string {
	return source.slice(node.from, node.to)
}

function parse(source: string): Tree {
	return typescriptLanguage.parser.parse(source)
}

function hasSyntaxError(tree: Tree): boolean {
	let hasError = false
	tree.iterate({ enter: (node) => void (hasError ||= node.type.isError) })
	return hasError
}

function findObject(tree: Tree): SyntaxNode | null {
	let object: SyntaxNode | null = null
	tree.iterate({ enter: (node) => void (object ||= node.name === "ObjectExpression" ? node.node : null) })
	return object
}

function addProp(source: string, props: ScriptProps, text: string): string {
	if (!props.propsObject) {
		// after the `{` of the default export
		const at = props.exportObject!.from + 1
		const rest = source.slice(at, props.exportObject!.to - 1).trim()
		return replaceRange(source, at, at, `\n\tprops: {\n\t\t${text},\n\t},${rest ? "" : "\n"}`)
	}
	const { from, to } = props.propsObject
	if (!props.propsObject.getChild("Property")) return replaceRange(source, from, to, `{\n\t\t${text},\n\t}`)
	return addProperty(source, props.propsObject, text)
}

/** Add `key: value` after the last property of an object literal that has one. `{}` gets `{ key: value }`. */
function addProperty(source: string, object: SyntaxNode, text: string): string {
	const last = object.getChildren("Property").at(-1)
	if (!last) return replaceRange(source, object.from, object.to, `{ ${text} }`)

	const indent = getIndent(source, last.from)
	// one property on each line, or all on one line, as the object already has them
	const separator = indent === null ? " " : `\n${indent}`
	const hasComma = last.nextSibling?.name === ","
	const at = hasComma ? last.nextSibling!.to : last.to
	return replaceRange(source, at, at, `${hasComma ? "" : ","}${separator}${text}${indent === null ? "" : ","}`)
}

function removeProperty(source: string, property: SyntaxNode): string {
	const hasComma = property.nextSibling?.name === ","
	const to = hasComma ? property.nextSibling!.to : property.to
	const indent = getIndent(source, property.from)
	// a property on its own line goes with the line
	if (indent !== null && source[to] === "\n") {
		return replaceRange(source, property.from - indent.length, to + 1, "")
	}
	// the last one of a line goes with the comma before it
	const previous = property.prevSibling
	const from = !hasComma && previous?.name === "," ? previous.from : property.from
	return replaceRange(source, from, hasComma && source[to] === " " ? to + 1 : to, "")
}

/** The whitespace before `position` on its line. Null when other text comes first. */
function getIndent(source: string, position: number): string | null {
	const lineStart = source.lastIndexOf("\n", position - 1) + 1
	const before = source.slice(lineStart, position)
	return before.trim() ? null : before
}

function replaceRange(source: string, from: number, to: number, text: string): string {
	return source.slice(0, from) + text + source.slice(to)
}
