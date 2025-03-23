<template>
	<div>
		<ContextMenu
			v-if="contextMenuVisible"
			v-on-click-outside="() => (contextMenuVisible = false)"
			:pos-x="posX"
			:pos-y="posY"
			:options="contextMenuOptions"
			@select="handleContextMenuSelect"
		/>
	</div>

	<FormDialog v-model:showDialog="showFormDialog" :block="block" />
</template>

<script setup lang="ts">
import { ref, Ref } from "vue"
import { vOnClickOutside } from "@vueuse/components"
import ContextMenu from "@/components/ContextMenu.vue"
import Block from "@/utils/block"
import useStudioStore from "@/stores/studioStore"
import useCanvasStore from "@/stores/canvasStore"
import { ContextMenuOption } from "@/types"
import { getComponentBlock, isObjectEmpty } from "@/utils/helpers"
import FormDialog from "@/components/FormDialog.vue"

const store = useStudioStore()
const canvasStore = useCanvasStore()

const contextMenuVisible = ref(false)
const posX = ref(0)
const posY = ref(0)

const block = ref(null) as unknown as Ref<Block>
const showFormDialog = ref(false)
const showContextMenu = (e: MouseEvent, refBlock: Block) => {
	block.value = refBlock
	if (block.value.isRoot()) return
	contextMenuVisible.value = true
	posX.value = e.pageX
	posY.value = e.pageY
	e.preventDefault()
	e.stopPropagation()
}

const handleContextMenuSelect = (action: CallableFunction) => {
	action()
	contextMenuVisible.value = false
}

const contextMenuOptions: ContextMenuOption[] = [
	{
		label: "Duplicate",
		action: () => block.value.duplicateBlock(),
	},
	{
		label: "Delete",
		action: () => {
			block.value.deleteBlock()
		},
		condition: () => {
			return !block.value.isRoot() && Boolean(block.value.getParentBlock())
		},
	},
	{
		label: "Wrap In Container",
		action: () => {
			const parentBlock = block.value.getParentBlock()
			if (!parentBlock) return

			const newBlockObj = getComponentBlock("FitContainer")
			if (block.value.isSlotBlock()) {
				newBlockObj.parentSlotName = block.value.parentSlotName
			}

			const selectedBlocks = canvasStore.activeCanvas?.selectedBlocks || []
			const blockPosition = Math.min(...selectedBlocks.map(parentBlock.getChildIndex.bind(parentBlock)))
			const newBlock = parentBlock?.addChild(newBlockObj, blockPosition)

			let width = null as string | null
			// move selected blocks to newBlock
			selectedBlocks
				.sort((a, b) => parentBlock.getChildIndex(a) - parentBlock.getChildIndex(b))
				.forEach((block) => {
					parentBlock?.removeChild(block)
					if (block.parentSlotName) {
						delete block.parentSlotName
					}
					newBlock?.addChild(block)
					if (!width) {
						const blockWidth = block.getStyle("width") as string | undefined
						if (blockWidth && (blockWidth == "auto" || blockWidth.endsWith("%"))) {
							width = "100%"
						}
					}
				})

			if (width) {
				newBlock?.setStyle("width", width)
			}

			if (newBlock) {
				newBlock.selectBlock()
			}
		},
	},
	{
		label: "Edit Slot",
		action: () => {
			store.showSlotEditorDialog = true
		},
		condition: () =>
			!isObjectEmpty(block.value.componentSlots) &&
			block.value.isSlotEditable(canvasStore.activeCanvas?.selectedSlot),
	},
	{
		label: "Add Fields from DocType",
		action: () => {
			showFormDialog.value = true
		},
	},
]

defineExpose({
	showContextMenu,
})
</script>
