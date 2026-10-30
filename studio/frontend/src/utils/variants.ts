/**
 * The variant sets on the current page and the option each one shows. A Variants block renders
 * one of its children. The choice is kept in the `v` query (v=<set>.<option>,…), so a link
 * carries any combination of options.
 */

import { computed, reactive, toRaw } from "vue"

export interface VariantSet {
	blockId: string
	name: string
	options: string[]
	// the option blocks' componentIds, in option order. A Variants block renders no element of
	// its own, so use the shown option's id to point at a set
	optionIds: (string | undefined)[]
	// this set's key in the `v` query, unique among the sets on the page
	token: string
}

// One row of a variants switcher. Each pill finds its own sets (VariantRows.vue).
export interface VariantRow {
	key: string
	name: string
	options: string[]
	activeIndex: number
}

// Sets rendered on the page, keyed by the Variants block's id. A Repeater mounts the same block
// once per row, so the copies are counted. The set leaves the pill when the last one unmounts.
const mountedSets = reactive<Map<string, VariantSet>>(new Map())
const mountCounts = new Map<string, number>()
const tokens = new Map<string, string>()

// Which option each Variants block shows on the editor canvas, keyed by block id. Only the
// editor writes it (variantsEditor.ts). In the renderer, the URL holds the choice.
const editorChoices = reactive<Map<string, number>>(new Map())

export function useMountedVariantSets() {
	return computed(() => [...mountedSets.values()])
}

export function retainVariantSet(blockId: string) {
	mountCounts.set(blockId, (mountCounts.get(blockId) || 0) + 1)
}

export function releaseVariantSet(blockId: string) {
	const remaining = (mountCounts.get(blockId) || 1) - 1
	if (remaining > 0) {
		mountCounts.set(blockId, remaining)
		return
	}
	mountCounts.delete(blockId)
	mountedSets.delete(blockId)
	tokens.delete(blockId)
}

/** Publish a rendered Variants block to the switcher pill. The block's render function calls
this, so the pill sees a rename or a new option. */
export function registerVariantSet(set: Omit<VariantSet, "token">): VariantSet {
	const registered = { ...set, token: variantToken(set.blockId, set.name) }
	// writing an unchanged set would re-render every pill. Read raw, so this comparison does not
	// make the renderer depend on the registry
	const current = toRaw(mountedSets).get(set.blockId)
	if (current && sameSet(current, registered)) return current
	mountedSets.set(set.blockId, registered)
	return registered
}

function sameSet(one: VariantSet, other: VariantSet): boolean {
	const sameNames = (a: (string | undefined)[], b: (string | undefined)[]) =>
		a.length === b.length && a.every((name, index) => name === b[index])
	return (
		one.name === other.name &&
		one.token === other.token &&
		sameNames(one.options, other.options) &&
		sameNames(one.optionIds, other.optionIds)
	)
}

/** The option a set shows. The editor's canvas choice wins if there is one, else the URL. */
export function activeVariantIndex(set: VariantSet, serialized: string): number {
	if (editorChoices.has(set.blockId)) return getEditorVariantChoice(set.blockId, set.options.length)
	const chosen = parseChoices(serialized)[set.token]
	const index = set.options.findIndex((option) => slug(option) === chosen)
	return index === -1 ? 0 : index
}

/** A set's key in the `v` query. Names are not unique: the first set to render keeps its name
as the key, and later sets use their block id. A key does not change while the set is on the
page, so a shared link keeps working. */
function variantToken(blockId: string, name: string): string {
	const token = tokens.get(blockId)
	if (token) return token
	const preferred = slug(name) || "variant"
	const resolved = [...tokens.values()].includes(preferred) ? slug(blockId) || preferred : preferred
	tokens.set(blockId, resolved)
	return resolved
}

/** The option the editor canvas shows for a block, clamped to the options it still has. */
export function getEditorVariantChoice(blockId: string, optionCount: number): number {
	return Math.min(editorChoices.get(blockId) ?? 0, Math.max(optionCount - 1, 0))
}

export function setEditorVariantChoice(blockId: string, index: number) {
	editorChoices.set(blockId, index)
}

/** The `v` query after choosing an option. The first option is the default and is left out. */
export function withChoice(serialized: string, token: string, options: string[], index: number): string {
	const choices = parseChoices(serialized)
	if (index <= 0) delete choices[token]
	else choices[token] = slug(options[index])
	return Object.entries(choices)
		.map(([setToken, option]) => `${setToken}.${option}`)
		.join(",")
}

function parseChoices(serialized: string): Record<string, string> {
	const choices: Record<string, string> = {}
	for (const entry of serialized.split(",")) {
		const [token, option] = entry.split(".")
		if (token && option) choices[token] = option
	}
	return choices
}

/** Option names live on the option blocks (`variantOptionName`). An unnamed block gets a
generic name. Every list of option names comes from here. */
export function variantOptionNames(block: {
	children?: ({ variantOptionName?: string } | undefined)[]
}): string[] {
	return (block.children || []).map(
		(child, index) => child?.variantOptionName || `Option ${index + 1}`,
	)
}

/** The Keep confirmation copy, shared by the viewer pill and the editor panel. */
export function keepDialogText(options: string[], keptIndex: number) {
	const others = options.filter((_, index) => index !== keptIndex).map((name) => `"${name}"`)
	const listed =
		others.length > 1 ? `${others.slice(0, -1).join(", ")} and ${others[others.length - 1]}` : others[0]
	return {
		title: `Keep "${options[keptIndex]}" variant?`,
		message: `This deletes the other ${listed} variant${others.length > 1 ? "s" : ""} from the page.`,
	}
}

export function slug(text: string): string {
	return (text || "")
		.toLowerCase()
		.replace(/[^a-z0-9]+/g, "-")
		.replace(/^-+|-+$/g, "")
}
