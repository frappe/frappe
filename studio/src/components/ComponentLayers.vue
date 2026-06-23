<template>
	<div ref="rootContainer" class="relative">
		<Draggable
			class="component-tree"
			:list="blocks"
			item-key="componentId"
			:group="{ name: 'component-tree', pull: 'clone', put: true }"
			@add="updateParent"
			:disabled="blocks.length && blocks[0].isRoot()"
			:force-fallback="true"
			:fallback-class="'!hidden'"
			:fallback-on-body="false"
			:delay="100"
			:delay-on-touch-only="false"
			:sort="false"
			:move="checkMove"
			@start="onDragStart"
			@end="onDragEnd"
		>
			<template #item="{ element }">
				<div
					:data-component-layer-id="element.componentId"
					:data-indent="indent"
					:title="element.componentId"
					class="component-layer-item relative min-w-24 cursor-pointer select-none rounded border border-transparent bg-surface-base bg-opacity-50 text-base text-ink-gray-6"
					:class="{
						'border-outline-blue-5 !bg-surface-blue-2 dark:!bg-surface-blue-10':
							canvasStore.layerDraggingOverBlock === element.componentId,
					}"
					@click.stop="openBlockEditor(element, $event)"
					@mouseover.stop="
						!canvasStore.isDragging && canvasStore.activeCanvas?.setHoveredBlock(element.componentId)
					"
					@mouseleave.stop="!canvasStore.isDragging && canvasStore.activeCanvas?.setHoveredBlock(null)"
				>
					<span
						class="group my-[7px] flex items-center gap-1.5 pr-[2px] font-medium"
						:style="{ paddingLeft: `${indent}px` }"
						:class="{
							'!opacity-50': !element.isVisible() || isParentHidden,
						}"
					>
						<FeatherIcon
							v-if="isExpandable(element)"
							:name="isExpanded(element) ? 'chevron-down' : 'chevron-right'"
							class="h-3 w-3"
							@click.stop="toggleExpanded(element)"
						/>
						<component
							:is="element.getIcon()"
							class="h-3 w-3"
							:class="{
								'text-ink-purple-6 opacity-80 dark:opacity-100 dark:brightness-125 dark:saturate-[0.3]':
									element.isStudioComponent,
							}"
						/>
						<span
							class="layer-label min-h-[1em] min-w-[2em] max-w-64 truncate"
							:class="{
								'text-ink-purple-6 opacity-80 dark:opacity-100 dark:brightness-125 dark:saturate-[0.3]':
									element.isStudioComponent,
							}"
							:contenteditable="element.editable"
							:title="element.blockId"
							@dblclick="element.editable = true"
							@keydown.enter.stop.prevent="element.editable = false"
							@blur="setBlockName($event, element)"
						>
							{{ element.getBlockDescription() }}
						</span>

						<!-- toggle visibility -->
						<div class="ml-auto flex items-center gap-2">
							<div
								v-if="element.hasVisibilityCondition()"
								title="Toggle visibility condition"
								class="invisible cursor-pointer group-hover:visible"
								@click.stop="element.toggleVisibilityCondition()"
							>
								<FeatherIcon :name="element.visibilityCondition ? 'zap' : 'zap-off'" class="h-3 w-3" />
							</div>
							<FeatherIcon
								v-if="!element.isRoot() && !isParentHidden"
								:name="element.isVisible() ? 'eye' : 'eye-off'"
								class="invisible mr-2 h-3 w-3 cursor-pointer group-hover:visible"
								@click.stop="element.toggleVisibility()"
							/>
						</div>
						<span v-if="element.isRoot()" class="ml-auto mr-2 text-sm capitalize text-ink-gray-4">
							{{ canvasStore.activeCanvas?.activeBreakpoint }}
						</span>
					</span>
					<div v-show="canShowChildLayer(element)">
						<ComponentLayers
							:blocks="element.children"
							:is-parent-hidden="isParentHidden || !element.isVisible()"
							:ref="childLayer"
							:indent="childIndent"
						/>
					</div>

					<div v-show="canShowSlotLayer(element)">
						<div
							v-for="(slot, slotName) in element.componentSlots"
							:key="slot.slotId"
							:data-slot-layer-id="slot.slotId"
							:title="slot.slotName"
							class="relative min-w-24 cursor-pointer select-none rounded border border-transparent bg-surface-base bg-opacity-50 text-base text-ink-gray-6"
							@click.stop="canvasStore.activeCanvas?.selectSlot(slot)"
						>
							<div
								class="group my-[7px] flex items-center gap-1.5 pr-[2px] font-medium"
								:style="{ paddingLeft: `${childIndent}px` }"
							>
								<FeatherIcon
									v-if="isSlotExpandable(slot, element)"
									:name="isSlotExpanded(slot) ? 'chevron-down' : 'chevron-right'"
									class="h-3 w-3"
									@click.stop="toggleSlotExpanded(slot)"
								/>
								<SlotIcon class="h-3 w-3" />
								<span class="min-h-[1em] min-w-[2em] truncate" :title="slot.slotName">#{{ slotName }}</span>
							</div>

							<div v-if="Array.isArray(slot.slotContent) && isSlotExpanded(slot)">
								<ComponentLayers :blocks="slot.slotContent" ref="slotLayer" :indent="slotIndent" />
							</div>
						</div>
					</div>
				</div>
			</template>
		</Draggable>
		<!-- Drop indicator line -->
		<div
			v-if="showDropIndicator"
			class="pointer-events-none absolute h-0.5 bg-surface-blue-6 transition-none"
			:style="{
				top: dropIndicatorTop + 'px',
				left: dropIndicatorLeft + 'px',
				width: 'calc(100% - ' + dropIndicatorLeft + 'px)',
			}"
		></div>
	</div>
</template>

<script setup lang="ts">
import { ref, watch, computed } from "vue"
import { FeatherIcon } from "frappe-ui"
import Draggable from "vuedraggable"

import ComponentLayers from "@/components/ComponentLayers.vue"

import useCanvasStore from "@/stores/canvasStore"
import Block from "@/utils/block"
import SlotIcon from "@/components/Icons/SlotIcon.vue"
import type { Slot } from "@/types"

type LayerInstance = InstanceType<typeof ComponentLayers>

const props = withDefaults(
	defineProps<{
		blocks: Block[]
		indent?: number
		isParentHidden?: boolean
	}>(),
	{
		blocks: () => [],
		indent: 10,
		isParentHidden: false,
	},
)

const canvasStore = useCanvasStore()
const rootContainer = ref<HTMLElement | null>(null)
const childLayers = ref<LayerInstance[]>([])
const childLayer = (el: LayerInstance) => {
	if (el) {
		childLayers.value.push(el)
	}
}

interface LayerBlock extends Block {
	editable: boolean
}

const setBlockName = (ev: Event, block: LayerBlock) => {
	const target = ev.target as HTMLElement
	block.blockName = target.innerText.trim()
	block.editable = false
}

// expand layers
const expandedLayers = ref(new Set(["root"]))
const childIndent = props.indent + 16

const isExpanded = (block: Block) => {
	return expandedLayers.value.has(block.componentId)
}

const toggleExpanded = (block: Block) => {
	if (block.isRoot()) {
		return
	}
	if (!blockExists(block)) {
		const child = childLayers.value.find((layer) => layer.blockExistsInTree(block)) as LayerInstance
		if (child) {
			child.toggleExpanded(block)
		}
	}
	if (isExpanded(block)) {
		expandedLayers.value.delete(block.componentId)
	} else {
		expandedLayers.value.add(block.componentId)
	}
}

const blockExists = (block: Block) => {
	return props.blocks.find((b) => b.componentId === block.componentId)
}

const blockExistsInTree = (block: Block): boolean => {
	if (blockExists(block)) {
		return true
	}
	for (const layer of childLayers.value) {
		if (layer.blockExistsInTree(block)) {
			return true
		}
	}
	return false
}

const canShowChildLayer = (block: Block) => {
	return isExpanded(block) && block.hasChildren()
}

const isExpandable = (block: Block) => {
	return (block.hasChildren() || block.hasComponentSlots()) && !block.isRoot()
}

// slots
const expandedSlots = ref<Set<string>>(new Set())

const isSlotExpanded = (slot: Slot) => {
	return expandedSlots.value.has(slot.slotId)
}

const isSlotExpandable = (slot: Slot, block: Block) => {
	return !block.isSlotEditable(slot) && slot.slotContent?.length > 0
}

const toggleSlotExpanded = (slot: Slot) => {
	if (expandedSlots.value.has(slot.slotId)) {
		expandedSlots.value.delete(slot.slotId)
	} else {
		expandedSlots.value.add(slot.slotId)
	}
}

const canShowSlotLayer = (block: Block) => {
	return isExpanded(block) && block.hasComponentSlots()
}

const openBlockEditor = (block: Block, e: MouseEvent) => {
	if (canvasStore.editingMode !== "fragment" && block.editInFragmentMode()) {
		const parentBlock = block.getParentBlock()
		canvasStore.editOnCanvas(
			block,
			(newBlock: Block) => parentBlock?.replaceChild(block, newBlock),
			`Save ${block.componentName}`,
		)
	} else {
		canvasStore.activeCanvas?.selectBlock(block, e, false, false)
	}
}

// --- Drag & drop reordering ---
interface DragState {
	draggedElement: HTMLElement | null
	hoverTarget: HTMLElement | null
	hoverPosition: "before" | "after" | "inside" | null
}

const showDropIndicator = ref(false)
const dropIndicatorTop = ref(0)
const dropIndicatorLeft = ref(0)
const dragState: DragState = { draggedElement: null, hoverTarget: null, hoverPosition: null }

const resetDropIndicators = () => {
	showDropIndicator.value = false
	canvasStore.layerDraggingOverBlock = null
}

const checkMove = () => false // Prevent automatic reordering

const onDragStart = (event: any) => {
	canvasStore.isDragging = true
	resetDropIndicators()
	dragState.draggedElement = event.item
	document.addEventListener("mousemove", onMouseMove)
}

const updateDropIndicator = (layerItem: HTMLElement, relativeY: number, elementHeight: number) => {
	if (!rootContainer.value) return

	const rect = layerItem.getBoundingClientRect()
	const containerRect = rootContainer.value.getBoundingClientRect()
	const indent = parseInt(layerItem.dataset.indent || "0", 10)
	const showAbove = relativeY < elementHeight / 2

	dropIndicatorTop.value = showAbove ? rect.top - containerRect.top : rect.bottom - containerRect.top
	dropIndicatorLeft.value = indent
	dragState.hoverPosition = showAbove ? "before" : "after"

	showDropIndicator.value = indent === 0 && showAbove ? false : true
}

const onMouseMove = (event: MouseEvent) => {
	const draggedElement = dragState.draggedElement
	if (!draggedElement) return

	const target = document.elementFromPoint(event.clientX, event.clientY)
	const layerItem = target?.closest(".component-layer-item") as HTMLElement | null

	if (!layerItem || layerItem === draggedElement || draggedElement.contains(layerItem)) {
		resetDropIndicators()
		return
	}

	const componentId = layerItem.dataset.componentLayerId
	const block = canvasStore.activeCanvas?.findBlock(componentId!)

	if (!block) {
		resetDropIndicators()
		return
	}

	const rect = layerItem.getBoundingClientRect()
	const relativeY = event.clientY - rect.top
	const elementHeight = rect.height
	const isInCenterZone = relativeY > elementHeight * 0.25 && relativeY < elementHeight * 0.75

	dragState.hoverTarget = layerItem

	if (block.canHaveChildren() && isInCenterZone) {
		// Highlight parent block for nested drop
		canvasStore.layerDraggingOverBlock = componentId!
		showDropIndicator.value = false
		dragState.hoverPosition = "inside"
	} else {
		// Show line indicator for sibling drop
		canvasStore.layerDraggingOverBlock = null
		updateDropIndicator(layerItem, relativeY, elementHeight)
	}
}

const removeFromParent = (block: Block) => {
	const parent = block.getParentBlock()
	if (parent) {
		parent.removeChild(block)
	}
}

const moveBlockInside = (draggedBlock: Block, targetBlock: Block) => {
	removeFromParent(draggedBlock)
	if (!targetBlock.children) targetBlock.children = []
	targetBlock.children.push(draggedBlock)
	draggedBlock.parentBlock = targetBlock
	delete draggedBlock.parentSlotName
}

const moveBlockAdjacent = (draggedBlock: Block, targetBlock: Block, position: "before" | "after") => {
	const targetParent = targetBlock.getParentBlock()
	if (!targetParent) return

	removeFromParent(draggedBlock)
	const targetIndex = targetParent.getChildIndex(targetBlock)
	const insertIndex = position === "before" ? targetIndex : targetIndex + 1

	draggedBlock.parentBlock = targetParent
	if (targetBlock.isSlotBlock()) {
		draggedBlock.parentSlotName = targetBlock.parentSlotName
		let slotContent = targetParent.getSlotContent(targetBlock.parentSlotName!)
		if (Array.isArray(slotContent)) {
			slotContent.splice(insertIndex, 0, draggedBlock)
		}
	} else {
		delete draggedBlock.parentSlotName
		targetParent.children.splice(insertIndex, 0, draggedBlock)
	}
}

const onDragEnd = (e: DragEvent) => {
	canvasStore.isDragging = false
	resetDropIndicators()
	document.removeEventListener("mousemove", onMouseMove)

	const { draggedElement, hoverTarget, hoverPosition } = dragState
	if (!draggedElement || !hoverTarget || !hoverPosition || draggedElement.contains(hoverTarget)) {
		Object.assign(dragState, { draggedElement: null, hoverTarget: null, hoverPosition: null })
		return
	}

	const draggedBlock = canvasStore.activeCanvas?.findBlock(draggedElement.dataset.componentLayerId!)
	const targetBlock = canvasStore.activeCanvas?.findBlock(hoverTarget.dataset.componentLayerId!)

	if (draggedBlock && targetBlock && draggedBlock !== targetBlock) {
		if (hoverPosition === "inside") {
			moveBlockInside(draggedBlock, targetBlock)
		} else {
			moveBlockAdjacent(draggedBlock, targetBlock, hoverPosition)
		}

		// Select the moved block
		canvasStore.activeCanvas?.selectBlock(draggedBlock, e)
	}

	Object.assign(dragState, { draggedElement: null, hoverTarget: null, hoverPosition: null })
}

// @ts-ignore
const updateParent = (event) => {
	const element = event.item.__draggable_context.element as Block
	const newParentLayerId = event.to.closest("[data-component-layer-id]")?.dataset.componentLayerId
	element.parentBlock = canvasStore.activeCanvas?.findBlock(newParentLayerId) ?? null

	// Check if moving into a slot
	const slotLayerId = event.to.closest("[data-slot-layer-id]")?.dataset.slotLayerId
	if (slotLayerId) {
		element.parentSlotName = slotLayerId.split(":")[1]
	} else {
		delete element.parentSlotName
	}
}

watch(
	() => canvasStore.activeCanvas?.selectedBlocks,
	() => {
		if (canvasStore.activeCanvas?.selectedBlocks.length) {
			canvasStore.activeCanvas?.selectedBlocks.forEach((block: Block) => {
				if (block) {
					let currentBlock = block
					// open all parent blocks and slots
					while (currentBlock && !currentBlock.isRoot()) {
						const parentBlock = currentBlock.getParentBlock()
						if (!parentBlock) break
						expandedLayers.value.add(parentBlock.componentId)

						const slotName = currentBlock.parentSlotName
						if (slotName) {
							const slotId = parentBlock.getSlot(slotName)?.slotId
							if (slotId) {
								expandedSlots.value.add(slotId)
							}
						}

						currentBlock = parentBlock
					}
				}
			})
		}
	},
	{ immediate: true, deep: true },
)

const slotIndent = computed(() => childIndent + 16)

defineExpose({
	toggleExpanded,
	blockExistsInTree,
})
</script>
