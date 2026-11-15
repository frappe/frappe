import { typescriptLanguage } from "@codemirror/lang-javascript"
import type { SyntaxNode } from "@lezer/common"

import type { StudioComponentInput } from "@/types/Studio/StudioComponent"

// The props of a component are in its script. The editor's form reads and writes the `props`
// object of the script's default export as text, so the rest of the script stays as written.

interface ScriptProps {
	/** Why the form cannot change the props. Empty when it can. */
	readOnlyReason: string
	exportObject?: SyntaxNode
	propsObject?: SyntaxNode
	entries: Map<string, SyntaxNode>
}

const NO_SCRIPT = "export default {}\n"

/** Whether the form can change the props of this script. If not, the reason to show. */
export function getPropsReadOnlyReason(source: string): string {
	return findScriptProps(source || NO_SCRIPT).readOnlyReason
}

/**
 * Add, change or remove one prop, and return the new script.
 * `previous` is the prop to replace, and `input` is its new definition. Pass only `input` to
 * add a prop, and only `previous` to remove one.
 */
export function setScriptProp(
	source: string,
	previous: StudioComponentInput | null,
	input: StudioComponentInput | null,
): string {
	source = source.trim() ? source : NO_SCRIPT
	const props = findScriptProps(source)
	if (props.readOnlyReason) throw new Error(props.readOnlyReason)

	const entry = previous && props.entries.get(previous.input_name)
	if (input && input.input_name !== previous?.input_name && props.entries.has(input.input_name)) {
		throw new Error(`A prop named "${input.input_name}" already exists.`)
	}
	const kept = entry && input && isSameDefault(previous, input) ? getDefaultSource(source, entry) : undefined
	const text = input ? getPropSource(input, kept) : ""

	let script: string
	if (entry) script = text ? replaceRange(source, entry.from, entry.to, text) : removeEntry(source, entry)
	else if (text) script = addEntry(source, props, text)
	else return source
	if (hasSyntaxError(script)) throw new Error("The default value is not valid JavaScript.")
	return script
}

const PROP_TYPES: Record<string, string | null> = {
	text: "String",
	textarea: "String",
	select: "String",
	color: "String",
	number: "Number",
	checkbox: "Boolean",
	code: null,
}

/** One entry of the `props` object, such as `size: { type: String, default: "md" }`. */
function getPropSource(input: StudioComponentInput, defaultSource?: string): string {
	const type = PROP_TYPES[input.type] ?? null
	const parts = type ? [`type: ${type}`] : []
	if (input.required) parts.push("required: true")
	defaultSource ??= getDefaultLiteral(input)
	if (defaultSource) parts.push(`default: ${defaultSource}`)

	const meta = []
	// String, Number and Boolean already name their control
	if (!["text", "number", "checkbox", "code"].includes(input.type)) meta.push(`type: "${input.type}"`)
	if (input.type === "select") meta.push(`options: ${JSON.stringify(getOptions(input))}`)
	if (input.description) meta.push(`description: ${JSON.stringify(input.description)}`)
	if (meta.length) parts.push(`meta: { ${meta.join(", ")} }`)

	const name = /^[A-Za-z_$][\w$]*$/.test(input.input_name) ? input.input_name : JSON.stringify(input.input_name)
	if (parts.length === 1 && type) return `${name}: ${type}`
	return `${name}: ${parts.length ? `{ ${parts.join(", ")} }` : "null"}`
}

function getDefaultLiteral(input: StudioComponentInput): string | undefined {
	const value = input.default
	if (value === undefined || value === null || value === "") return undefined
	if (input.type === "number") {
		if (!Number.isFinite(Number(value))) throw new Error("The default value must be a number.")
		return String(Number(value))
	}
	// Vue gives a Boolean prop without a default the value false
	if (input.type === "checkbox") return ["true", "1"].includes(String(value)) ? "true" : undefined
	if (input.type === "select" && !getOptions(input).includes(String(value))) {
		throw new Error("The default value must be one of the options.")
	}
	// Vue calls a factory for each instance, so two instances do not share one object
	if (input.type === "code") return `() => (${value})`
	return JSON.stringify(value)
}

function getOptions(input: StudioComponentInput): string[] {
	return (input.options || "").split("\n").filter((option) => option.trim())
}

// The script gives a default as text, and a number or checkbox control gives a number or a boolean.
function isSameDefault(previous: StudioComponentInput, input: StudioComponentInput): boolean {
	return String(previous.default ?? "") === String(input.default ?? "") && previous.type === input.type
}

/** The text of an entry's `default`, so a value that the form cannot show, such as a factory, stays. */
function getDefaultSource(source: string, entry: SyntaxNode): string | undefined {
	const value = getPropertyValue(entry)
	if (value?.name !== "ObjectExpression") return undefined
	const defaultValue = getPropertyValue(getProperties(source, value).get("default"))
	return defaultValue ? source.slice(defaultValue.from, defaultValue.to) : undefined
}

function findScriptProps(source: string): ScriptProps {
	const none = (readOnlyReason: string): ScriptProps => ({ readOnlyReason, entries: new Map() })
	if (hasSyntaxError(source)) return none("Fix the syntax error in the script first.")

	const tree = typescriptLanguage.parser.parse(source)
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
		if (key?.name === "PropertyDefinition") properties.set(source.slice(key.from, key.to), property)
		else if (key?.name === "String") properties.set(source.slice(key.from + 1, key.to - 1), property)
	}
	return properties
}

/** The value of `name: value`. A shorthand or a method has none. */
function getPropertyValue(property: SyntaxNode | undefined): SyntaxNode | null {
	return property?.getChild(":")?.nextSibling ?? null
}

function hasSyntaxError(source: string): boolean {
	let hasError = false
	typescriptLanguage.parser.parse(source).iterate({ enter: (node) => void (hasError ||= node.type.isError) })
	return hasError
}

function addEntry(source: string, props: ScriptProps, text: string): string {
	if (!props.propsObject) {
		// after the `{` of the default export
		const at = props.exportObject!.from + 1
		const rest = source.slice(at, props.exportObject!.to - 1).trim()
		return replaceRange(source, at, at, `\n\tprops: {\n\t\t${text},\n\t},${rest ? "" : "\n"}`)
	}
	const entries = props.propsObject.getChildren("Property")
	const last = entries.at(-1)
	if (!last) return replaceRange(source, props.propsObject.from, props.propsObject.to, `{\n\t\t${text},\n\t}`)

	const indent = getIndent(source, last.from)
	// one entry on each line, or all on one line, as the script already has them
	const separator = indent === null ? " " : `\n${indent}`
	const hasComma = last.nextSibling?.name === ","
	const at = hasComma ? last.nextSibling!.to : last.to
	return replaceRange(source, at, at, `${hasComma ? "" : ","}${separator}${text}${indent === null ? "" : ","}`)
}

function removeEntry(source: string, entry: SyntaxNode): string {
	const to = entry.nextSibling?.name === "," ? entry.nextSibling.to : entry.to
	const indent = getIndent(source, entry.from)
	// an entry on its own line goes with the line
	if (indent !== null && source[to] === "\n") return replaceRange(source, entry.from - indent.length, to + 1, "")
	return replaceRange(source, entry.from, source[to] === " " ? to + 1 : to, "")
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
