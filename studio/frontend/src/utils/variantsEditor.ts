/**
 * Variants helpers that only the editor uses. They reach into the canvas — the block tree, the
 * selection, the undo history — so they stay out of `variants.ts`, which the renderer imports.
 */

import { dialog, toast } from "frappe-ui"
import useCanvasStore from "@/stores/canvasStore"
import type Block from "@/utils/block"
import { keepDialogText, setEditorVariantChoice } from "@/utils/variants"

/** Confirm and collapse a Variants block to one of its options — a local canvas edit,
unlike the viewer pill's server call, so undo and autosave treat it like any other
block change. */
export function confirmKeepVariantOption(target: Block, index: number) {
	const options = variantOptionNames(target)
	const kept = options[index] || `Option ${index + 1}`
	dialog.confirm({
		...keepDialogText(options, index),
		confirmLabel: "Keep",
		onConfirm: async () => {
			const parentBlock = target.getParentBlock()
			const chosen = target.children[index]
			if (!parentBlock || !chosen) throw new Error("This option has no block to keep")
			const childIndex = parentBlock.getChildIndex(target)
			const keep = () => {
				parentBlock.removeChild(target)
				// the block leaves the set, so it is no longer an option of anything
				chosen.variantOptionName = undefined
				parentBlock.insertChild(chosen, childIndex, target.parentSlotName)
				chosen.selectBlock()
			}
			// batched, so selecting the kept block doesn't bleed into the pre-keep
			// history record and undo reselects the Variants block
			const history = useCanvasStore().activeCanvas?.history
			history ? history.batch(keep) : keep()
			toast.success(`Kept "${kept}"`)
		},
	})
}

/** Keep the selection visible: when the selected block sits inside a Variants option that
isn't the one on canvas, switch that Variants block to the option holding it. */
export function revealVariantOption(block: Block) {
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
