import { useStorage } from "@vueuse/core"
import type Block from "@/utils/block"
import type { BlockStyles } from "@/types"

const copiedStyle = useStorage<{ componentId: string; styles: BlockStyles | null }>(
	"studio-copied-style",
	{ componentId: "", styles: null },
	sessionStorage,
)

export function copyBlockStyles(block: Block) {
	copiedStyle.value = { componentId: block.componentId, styles: block.getStylesCopy() }
}

export function canPasteStylesTo(block: Block) {
	if (!copiedStyle.value.styles) return false
	// every page's root has the same id, so a root copied on one page can style another's
	return block.isRoot() || copiedStyle.value.componentId !== block.componentId
}

export function pasteBlockStyles(block: Block) {
	if (!canPasteStylesTo(block)) return
	block.updateStyles(copiedStyle.value.styles!)
}
