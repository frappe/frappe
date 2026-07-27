<template>
	<div>
		<ContextMenu
			v-if="contextMenuVisible"
			:pos-x="posX"
			:pos-y="posY"
			:options="contextMenuOptions"
			@select="handleContextMenuSelect"
			@close="contextMenuVisible = false"
		/>
		<FormDialog v-if="block" v-model:showDialog="showFormDialog" :block="block" />
	</div>
</template>

<script setup lang="ts">
import { ref, Ref } from "vue"
import ContextMenu from "@/components/ContextMenu.vue"
import Block from "@/utils/block"
import useCanvasStore from "@/stores/canvasStore"
import useComponentEditorStore from "@/stores/componentEditorStore"
import type { ContextMenuOption, ContextMenuGroup } from "@/types"
import { getBlockCopy, getComponentBlock } from "@/utils/serializer"
import getBlockTemplate from "@/utils/blockTemplate"
import FormDialog from "@/components/FormDialog.vue"
import components from "@/data/components"
import { toast } from "frappe-ui"

const canvasStore = useCanvasStore()

const contextMenuVisible = ref(false)
const posX = ref(0)
const posY = ref(0)

const block = ref(null) as unknown as Ref<Block>
const showFormDialog = ref(false)
const showContextMenu = (e: MouseEvent, refBlock: Block) => {
	block.value = refBlock
	if (block.value.isRoot()) return
	// remember the right-clicked slot so "Add Component" drops into it
	const slot = canvasStore.activeCanvas?.selectedSlot
	addTargetSlot.value = slot && slot.parentBlockId === refBlock.componentId ? slot.slotName : null
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

// Add Component via the context menu — an alternative to drag & drop, useful when a slot's
// drop target is too small to hit. Rendered as a grouped submenu (Core / Frappe UI / Framework UI).
const addTargetSlot = ref<string | null>(null)

const buildComponentSubmenu = (): ContextMenuGroup[] => {
	const list = components.list as any[]
	const toOptions = (group: any[]): ContextMenuOption[] =>
		group.map((component) => ({
			label: component.title,
			icon: component.icon,
			action: () => addComponent(component.name),
		}))
	const groups: ContextMenuGroup[] = [
		{
			label: "Core",
			options: toOptions(
				list.filter(
					(c) => !components.isFrappeUIComponent(c.name) && !components.isFrameworkUIComponent(c.name),
				),
			),
		},
		{ label: "Frappe UI", options: toOptions(list.filter((c) => components.isFrappeUIComponent(c.name))) },
	]
	// @framework/ui isn't shipped on older frappe — hide its components entirely.
	if (components.isFrameworkUIAvailable()) {
		groups.push({
			label: "Framework UI",
			options: toOptions(list.filter((c) => components.isFrameworkUIComponent(c.name))),
		})
	}
	return groups.filter((group) => group.options.length)
}

// only shown when the target can accept children (see the "Add Component" condition),
// so the new block always drops straight in — into the right-clicked slot if there was one.
const addComponent = (componentName: string) => {
	const targetBlock = block.value
	if (!targetBlock) return
	const newBlock = getComponentBlock(componentName)
	if (addTargetSlot.value) {
		newBlock.parentSlotName = addTargetSlot.value
	}
	targetBlock.addChild(newBlock)
}

const contextMenuOptions: ContextMenuOption[] = [
	{
		label: "Add Component",
		condition: () => Boolean(block.value?.canHaveChildren()),
		submenu: buildComponentSubmenu(),
	},
	{
		label: "Wrap In Container",
		action: () => {
			const parentBlock = block.value.getParentBlock()
			if (!parentBlock) return

			const newBlockObj = getBlockTemplate("fit-container")
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
					// Remove from parent first
					parentBlock?.removeChild(block)
					// Clear slot reference before adding to container
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
		label: "Repeat Block",
		action: () => {
			const repeaterBlockObj = getComponentBlock("Repeater")
			repeaterBlockObj.addSlot("default")
			const parentBlock = block.value.getParentBlock()
			if (!parentBlock) return
			const repeaterBlock = parentBlock.addChild(repeaterBlockObj, parentBlock.getChildIndex(block.value))
			if (repeaterBlock) {
				const blockCopy = getBlockCopy(block.value)
				blockCopy.parentSlotName = "default"
				repeaterBlock.addChild(blockCopy, 0)
				parentBlock.removeChild(block.value)
				repeaterBlock.selectBlock()
				toast.warning("Please set data & data key for the repeater block")
			}
		},
		condition: () => !block.value.isRoot() && !block.value.isRepeater(),
	},
	{ label: "Copy", action: () => document.execCommand("copy") },
	{
		label: "Duplicate",
		action: () => block.value.duplicateBlock(),
	},
	{
		label: "Save as Component",
		action: () => {
			useComponentEditorStore().promptNewComponent({
				block: block.value,
				onCreated: (component) => block.value.extendFromComponent(component.component_id),
			})
		},
		condition: () => !block.value.isStudioComponent,
	},
	{
		label: "Edit Component",
		action: () => {
			const componentEditorStore = useComponentEditorStore()
			componentEditorStore.editComponent(block.value.componentName as string)
		},
		condition: () => Boolean(block.value.isStudioComponent),
	},
	{
		label: "Add Fields from DocType",
		action: () => {
			showFormDialog.value = true
		},
	},
	{
		label: "Reset Style Overrides",
		condition: () => canvasStore.activeCanvas?.activeBreakpoint !== "desktop",
		disabled: () => !block.value?.hasOverrides(canvasStore.activeCanvas?.activeBreakpoint || "desktop"),
		action: () => {
			block.value.resetOverrides(canvasStore.activeCanvas?.activeBreakpoint || "desktop")
		},
	},
	{
		label: "Delete",
		theme: "red",
		action: () => {
			block.value.deleteBlock()
		},
		condition: () => {
			return !block.value.isRoot() && Boolean(block.value.getParentBlock())
		},
	},
]

defineExpose({
	showContextMenu,
})
</script>
