/**
 * Variant sets rendered on the current page, and their URL-mirrored choices. A Variants block
 * renders one of its children; the choice rides the `v` query (v=<set>.<option>,…) so any
 * combination of options is a shareable link.
 */

import { computed, reactive, toRaw } from "vue"

export interface VariantSet {
	blockId: string
	name: string
	options: string[]
	// the option blocks' componentIds, in option order — the Variants block renders no wrapper
	// element, so pointing at a set on the page means pointing at its rendered option
	optionIds: (string | undefined)[]
	// this set's key in the `v` query, unique among the sets on the page
	token: string
}

// One row of a variants switcher, however the surface resolves its sets (VariantRows.vue)
export interface VariantRow {
	key: string
	name: string
	options: string[]
	activeIndex: number
}

// Sets rendered on the page, keyed by the Variants block's id. A Repeater mounts the same
// block once per row, so copies are counted and a set leaves the pill with its last one.
const mountedSets = reactive<Map<string, VariantSet>>(new Map())
const mountCounts = new Map<string, number>()
const tokens = new Map<string, string>()

// Which option each Variants block shows on the editor canvas, keyed by block id. Only the
// editor writes it (variantsEditor.ts); in the renderer the URL stays the single source of truth.
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

/** Publish a rendered Variants block to the switcher pill. Called from the block's render
function, so a rename or an added option reaches the pill. */
export function registerVariantSet(set: Omit<VariantSet, "token">): VariantSet {
	const registered = { ...set, token: variantToken(set.blockId, set.name) }
	// a render writing an unchanged set would invalidate every pill reading the registry,
	// and the raw read keeps the comparison from making the renderer depend on it
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

/** The option a set shows: the editor's canvas choice when one is set, the URL otherwise. */
export function activeVariantIndex(set: VariantSet, serialized: string): number {
	if (editorChoices.has(set.blockId)) return getEditorVariantChoice(set.blockId, set.options.length)
	const chosen = parseChoices(serialized)[set.token]
	const index = set.options.findIndex((option) => slug(option) === chosen)
	return index === -1 ? 0 : index
}

/** A set's key in the `v` query. Names are not unique, so only the first set to render keeps
its name as the key and the rest fall back to their block id. The key then stays put while the
set is on the page, so a link shared from it keeps working. */
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

/** The `v` query after choosing an option; the first option is the default and stays out of it. */
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

/** Option names live on the option blocks (`variantOptionName`); an unnamed block
still gets a stable generic name. Every list of option names comes from here. */
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
