/**
 * Variant sets mounted on the current page, and their URL-mirrored choices. A Variants block
 * renders one of its children; the choice rides the `v` query (v=<set>.<option>,…) so any
 * combination of options is a shareable link.
 */

import { computed, reactive, type ComputedRef } from "vue"
import { useRoute } from "vue-router"

export interface VariantSet {
	key: string
	name: string
	options: string[]
	blockId?: string
	// the option blocks' componentIds, in option order — the Variants block renders no wrapper
	// element, so pointing at a set on the page means pointing at its rendered option
	optionIds?: (string | undefined)[]
}

const mountedSets = reactive<Map<string, VariantSet>>(new Map())

// Editor-only: which option each Variants block shows on the canvas, keyed by block id.
// The renderer bundle never writes it, so there the URL stays the single source of truth.
const editorChoices = reactive<Map<string, number>>(new Map())

export function useMountedVariantSets() {
	return computed(() => [...mountedSets.values()])
}

/** Register a mounted Variants block and resolve its active option: the editor's canvas
choice when one is set, the URL otherwise. */
export function useVariantSet(set: {
	name: string
	options: string[]
	blockId?: string
	optionIds?: (string | undefined)[]
}): { key: string; activeIndex: ComputedRef<number> } {
	const route = useRoute()
	const key = slug(set.name) || "variant"
	mountedSets.set(key, {
		key,
		name: set.name || "Variant",
		options: set.options,
		blockId: set.blockId,
		optionIds: set.optionIds,
	})
	const activeIndex = computed(() => {
		const editorChoice = set.blockId ? editorChoices.get(set.blockId) : undefined
		if (editorChoice !== undefined) return editorChoice
		return choiceIndex(String(route?.query?.v ?? ""), key, set.options)
	})
	return { key, activeIndex }
}

export function getEditorVariantChoice(blockId: string): number {
	return editorChoices.get(blockId) ?? 0
}

export function setEditorVariantChoice(blockId: string, index: number) {
	editorChoices.set(blockId, index)
}

interface EditorBlock {
	componentId: string
	componentName: string
	children: EditorBlock[]
	getParentBlock: () => EditorBlock | null
}

/** Keep the selection visible: when the selected block sits inside a Variants option that
isn't the one on canvas, switch that Variants block to the option holding it. */
export function revealVariantOption(block: EditorBlock) {
	let child = block
	let parent = child.getParentBlock?.()
	while (parent) {
		if (parent.componentName === "Variants") {
			const index = parent.children.indexOf(child)
			if (index !== -1) setEditorVariantChoice(parent.componentId, index)
		}
		child = parent
		parent = child.getParentBlock?.()
	}
}

/** Option names live on the option blocks (`variantOptionName`); an unnamed block
still gets a stable generic name. */
export function variantOptionNames(block: {
	children?: ({ variantOptionName?: string } | undefined)[]
}): string[] {
	return (block.children || []).map(
		(child, index) => child?.variantOptionName || `Option ${index + 1}`,
	)
}

export function releaseVariantSet(key: string) {
	mountedSets.delete(key)
}

export function choiceIndex(serialized: string, key: string, options: string[]): number {
	const chosen = parseChoices(serialized)[key]
	const index = options.findIndex((option) => slug(option) === chosen)
	return index === -1 ? 0 : index
}

/** The `v` query after choosing an option; the first option is the default and stays out of it. */
export function withChoice(serialized: string, key: string, options: string[], index: number): string {
	const choices = parseChoices(serialized)
	if (index <= 0) delete choices[key]
	else choices[key] = slug(options[index])
	return Object.entries(choices)
		.map(([setKey, option]) => `${setKey}.${option}`)
		.join(",")
}

function parseChoices(serialized: string): Record<string, string> {
	const choices: Record<string, string> = {}
	for (const entry of serialized.split(",")) {
		const [key, option] = entry.split(".")
		if (key && option) choices[key] = option
	}
	return choices
}

/** The Keep confirmation copy, shared by the viewer pill and the editor panel. */
export function keepDialogText(options: string[], keptIndex: number) {
	const named = options.map((name, index) => name || `Option ${index + 1}`)
	const others = named.filter((_, index) => index !== keptIndex).map((name) => `"${name}"`)
	const listed =
		others.length > 1 ? `${others.slice(0, -1).join(", ")} and ${others[others.length - 1]}` : others[0]
	return {
		title: `Keep "${named[keptIndex]}" variant?`,
		message: `This deletes the other variant${others.length > 1 ? "s" : ""} ${listed} from the page.`,
	}
}

export function slug(text: string): string {
	return (text || "")
		.toLowerCase()
		.replace(/[^a-z0-9]+/g, "-")
		.replace(/^-+|-+$/g, "")
}
