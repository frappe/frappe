<template>
	<div>
		<ContextMenu ref="contextMenuRef" :options="contextMenuOptions" @select="handleContextMenuSelect" />
		<FormDialog v-if="block" v-model:showDialog="showFormDialog" :block="block" />
	</div>
</template>

<script setup lang="ts">
import { ref, computed, Ref } from "vue"
import ContextMenu from "@/components/ContextMenu.vue"
import Block from "@/utils/block"
import useCanvasStore from "@/stores/canvasStore"
import useStudioStore from "@/stores/studioStore"
import useComponentEditorStore from "@/stores/componentEditorStore"
import type { ContextMenuOption, ContextMenuGroup, FrappeUIComponent } from "@/types"
import type { StudioComponent } from "@/types/Studio/StudioComponent"
import { getBlockCopy, getBlockInstance, getComponentBlock } from "@/utils/serializer"
import getBlockTemplate from "@/utils/blockTemplate"
import FormDialog from "@/components/FormDialog.vue"
import components from "@/data/components"
import { studioComponents } from "@/data/studioComponents"
import { toast } from "frappe-ui"
import LucideCode from "~icons/lucide/code"
import LucideBox from "~icons/lucide/box"

const canvasStore = useCanvasStore()
const store = useStudioStore()

const contextMenuRef = ref<InstanceType<typeof ContextMenu> | null>(null)

const block = ref(null) as unknown as Ref<Block>
const showFormDialog = ref(false)

const selectedSlot = ref<string | null>(null)
const showContextMenu = (e: MouseEvent, refBlock: Block) => {
	block.value = refBlock
	// remember the right-clicked slot so "Add Component" drops into it
	const slot = canvasStore.activeCanvas?.selectedSlot
	selectedSlot.value = slot && slot.parentBlockId === refBlock.componentId ? slot.slotName : null
	e.preventDefault()
	e.stopPropagation()
	contextMenuRef.value?.show(e.pageX, e.pageY)
}

const handleContextMenuSelect = (action: CallableFunction) => {
	action()
}

const addComponent = (
	componentName: string,
	{ isStudioComponent = false, isCustomVueComponent = false } = {},
) => {
	const targetBlock = block.value
	if (!targetBlock) return
	// Compound components (List, Settings Dialog, Header) drop their whole tree via
	// a block template, mirroring canvas drag-drop; the rest add a single block.
	const blockTemplate = components.get(componentName)?.blockTemplate
	const newBlock = blockTemplate
		? getBlockInstance(getBlockTemplate(blockTemplate as any))
		: getComponentBlock(componentName, isStudioComponent, isCustomVueComponent)
	if (selectedSlot.value) {
		newBlock.parentSlotName = selectedSlot.value
	}
	targetBlock.addChild(newBlock)
}

const componentSubmenu = computed<ContextMenuGroup[]>(() => {
	const toOption = (component: FrappeUIComponent): ContextMenuOption => ({
		label: component.title,
		icon: component.icon,
		action: () => addComponent(component.name),
	})

	const groups: ContextMenuGroup[] = components.getComponentGroups(components.list).map((group) => ({
		label: group.label,
		options: group.components
			.filter((component) => !component.group)
			.flatMap((component) => [
				toOption(component),
				...(component.isGroup
					? components
							.getParts(component.name)
							.filter((part) => block.value?.canAddChild(part))
							.map(toOption)
					: []),
			]),
	}))

	if (store.customVueComponents?.length) {
		groups.push({
			label: "Vue Components",
			options: store.customVueComponents.map((component) => ({
				label: component.component_name,
				icon: LucideCode,
				action: () => addComponent(component.component_name, { isCustomVueComponent: true }),
			})),
		})
	}

	if (studioComponents.data?.length) {
		groups.push({
			label: "Studio Components",
			options: studioComponents.data.map((component: StudioComponent) => ({
				label: component.component_name,
				icon: LucideBox,
				action: () => addComponent(component.component_id, { isStudioComponent: true }),
			})),
		})
	}

	return groups
})

const contextMenuOptions: ContextMenuOption[] = [
	{
		label: "Add Component",
		condition: () => Boolean(block.value?.canHaveChildren()),
		get submenu() {
			return componentSubmenu.value
		},
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
		condition: () => Boolean(block.value.getParentBlock()),
	},
	{
		label: "Unwrap",
		action: () => unwrapBlock(),
		condition: () => canUnwrap(),
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
		condition: () => Boolean(block.value.getParentBlock()) && !block.value.isRepeater(),
	},
	{ label: "Copy", action: () => document.execCommand("copy") },
	{
		label: "Duplicate",
		action: () => block.value.duplicateBlock(),
		condition: () => Boolean(block.value.getParentBlock()),
	},
	{
		label: "Save as Component",
		action: () => {
			useComponentEditorStore().promptNewComponent({
				block: block.value,
				onCreated: (component) => block.value.extendFromComponent(component.component_id),
			})
		},
		condition: () => !block.value.isStudioComponent && Boolean(block.value.getParentBlock()),
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

function canUnwrap() {
	const target = block.value
	if (target.isRoot() || !target?.isContainer() || !target.hasChildren()) return false
	// a component root has no parent to leave its children with, so only a lone child can take its place
	return Boolean(target.getParentBlock()) || target.children.length === 1
}

function unwrapBlock() {
	const target = block.value
	const parentBlock = target.getParentBlock()
	const children = [...target.children]

	if (!parentBlock) {
		promoteToRoot(children[0], target)
		return
	}

	let index = parentBlock.getChildIndex(target) ?? parentBlock.children.length
	children.forEach((child) => {
		target.removeChild(child)
		child.parentSlotName = target.parentSlotName
		parentBlock.addChild(child, index++, false)
	})
	parentBlock.removeChild(target)
	children[0]?.selectBlock()
}

function promoteToRoot(newRoot: Block, target: Block) {
	target.removeChild(newRoot)
	newRoot.parentBlock = null
	delete newRoot.parentSlotName
	// keep the history so unwrapping stays undoable and still marks the canvas dirty
	canvasStore.activeCanvas?.setRootBlock(newRoot, false, false)
	newRoot.selectBlock()
}

defineExpose({
	showContextMenu,
})
</script>
