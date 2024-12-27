<template>
	<div>
		<slot :onContextMenu="showContextMenu" />
		<ContextMenu
			v-if="contextMenuVisible"
			v-on-click-outside="() => (contextMenuVisible = false)"
			:pos-x="posX"
			:pos-y="posY"
			:options="contextMenuOptions"
			@select="handleContextMenuSelect"
		/>
	</div>
</template>

<script setup lang="ts">
import { ref } from "vue"
import { vOnClickOutside } from "@vueuse/components"
import ContextMenu from "@/components/ContextMenu.vue"
import Block from "@/utils/block"
import useStudioStore from "@/stores/studioStore"
import { ContextMenuOption } from "@/types"
import { getComponentBlock, isObjectEmpty } from "@/utils/helpers"

const props = defineProps<{
	block: Block
	editable: boolean
}>()

const store = useStudioStore()

const contextMenuVisible = ref(false)
const posX = ref(0)
const posY = ref(0)

const showContextMenu = (e: MouseEvent) => {
	if (props.block.isRoot() || props.editable) return
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
		action: () => props.block.duplicateBlock(),
	},
	{
		label: "Delete",
		action: () => {
			props.block.deleteBlock()
		},
		condition: () => {
			return !props.block.isRoot() && Boolean(props.block.getParentBlock())
		},
	},
	{
		label: "Wrap In Container",
		action: () => {
			const newBlockObj = getComponentBlock("FitContainer")
			const parentBlock = props.block.getParentBlock()
			if (!parentBlock) return

			const selectedBlocks = store.selectedBlocks || []
			const blockPosition = Math.min(...selectedBlocks.map(parentBlock.getChildIndex.bind(parentBlock)))
			const newBlock = parentBlock?.addChild(newBlockObj, blockPosition)

			let width = null as string | null
			// move selected blocks to newBlock
			selectedBlocks
				.sort((a, b) => parentBlock.getChildIndex(a) - parentBlock.getChildIndex(b))
				.forEach((block) => {
					parentBlock?.removeChild(block)
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
			!isObjectEmpty(props.block.componentSlots) && props.block.isSlotEditable(store.selectedSlot),
	},
]
</script>
