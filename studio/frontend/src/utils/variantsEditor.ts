/**
 * Variants helpers that only the editor uses. They work on the canvas: the block tree, the
 * selection and the undo history. They stay out of `variants.ts`, which the renderer imports.
 */

import { dialog, toast } from "frappe-ui"
import useCanvasStore from "@/stores/canvasStore"
import type Block from "@/utils/block"
import { keepDialogText, setEditorVariantChoice, variantOptionNames } from "@/utils/variants"

/** Confirm, then collapse a Variants block to one of its options. This edits the canvas, not
the server, so undo and autosave treat it like any other block change. */
export function confirmKeepVariantOption(target: Block, index: number) {
	const options = variantOptionNames(target)
	const kept = options[index]
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
				chosen.variantOptionName = undefined
				parentBlock.insertChild(chosen, childIndex, target.parentSlotName)
				chosen.selectBlock()
			}
			// batched, so the new selection joins this record and not the one before it.
			// Undo then reselects the Variants block
			const history = useCanvasStore().activeCanvas?.history
			history ? history.batch(keep) : keep()
			toast.success(`Kept "${kept}"`)
		},
	})
}

/** Keep the selected block visible. If it sits in an option the canvas does not show, switch
that Variants block to the option that holds it. */
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
