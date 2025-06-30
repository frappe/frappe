<template>
	<div>
		<Draggable
			class="component-tree"
			:list="blocks"
			item-key="componentId"
			:group="{ name: 'component-tree' }"
			@add="updateParent"
			:disabled="blocks.length && blocks[0].isRoot()"
			ghost-class="opacity-50"
		>
			<template #item="{ element }">
				<div>
					<div
						:data-component-layer-id="element.componentId"
						:title="element.componentId"
						class="min-w-24 cursor-pointer overflow-hidden rounded border border-transparent bg-white bg-opacity-50 text-base text-gray-700"
						@click.stop="openBlockEditor(element, $event)"
						@mouseover.stop="canvasStore.activeCanvas?.setHoveredBlock(element.componentId)"
						@mouseleave="canvasStore.activeCanvas?.setHoveredBlock(null)"
					>
						<span
							class="group my-[7px] flex items-center gap-1.5 pr-[2px] font-medium"
							:style="{ paddingLeft: `${indent}px` }"
							:class="{
								'!opacity-50': !element.isVisible(),
							}"
						>
							<FeatherIcon
								v-if="isExpandable(element)"
								:name="isExpanded(element) ? 'chevron-down' : 'chevron-right'"
								class="h-3 w-3"
								@click.stop="toggleExpanded(element)"
							/>
							<component :is="element.getIcon()" class="h-3 w-3" />
							<span
								class="min-h-[1em] min-w-[2em] truncate"
								:contenteditable="element.editable"
								:title="element.blockId"
								@dblclick="element.editable = true"
								@keydown.enter.stop.prevent="element.editable = false"
								@blur="setBlockName($event, element)"
							>
								{{ element.getBlockDescription() }}
							</span>

							<!-- toggle visibility -->
							<FeatherIcon
								v-if="!element.isRoot()"
								:name="element.isVisible() ? 'eye' : 'eye-off'"
								class="ml-auto mr-2 hidden h-3 w-3 group-hover:block"
								@click.stop="element.toggleVisibility()"
							/>
							<span v-if="element.isRoot()" class="ml-auto mr-2 text-sm capitalize text-gray-500">
								{{ canvasStore.activeCanvas?.activeBreakpoint }}
							</span>
						</span>
						<div v-show="canShowChildLayer(element)">
							<ComponentLayers :blocks="element.children" ref="childLayer" :indent="childIndent" />
						</div>

						<div v-show="canShowSlotLayer(element)">
							<div
								v-for="(slot, slotName) in element.componentSlots"
								:key="slot.slotId"
								:data-slot-layer-id="slot.slotId"
								:title="slot.slotName"
								class="min-w-24 cursor-pointer overflow-hidden rounded border border-transparent bg-white bg-opacity-50 text-base text-gray-700"
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
				</div>
			</template>
		</Draggable>
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

const props = withDefaults(
	defineProps<{
		blocks: Block[]
		indent?: number
	}>(),
	{
		blocks: () => [],
		indent: 10,
	},
)

const canvasStore = useCanvasStore()
const childLayer = ref<InstanceType<typeof ComponentLayers> | null>(null)

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
	const blockIndex = props.blocks.findIndex((b) => b.componentId === block.componentId)
	if (blockIndex === -1) {
		childLayer.value?.toggleExpanded(block)
		return
	}
	if (isExpanded(block) && !block.isRoot()) {
		expandedLayers.value.delete(block.componentId)
	} else {
		expandedLayers.value.add(block.componentId)
	}
}

const canShowChildLayer = (block: Block) => {
	return isExpanded(block) && block.hasChildren()
}

const isExpandable = (block: Block) => {
	return block.hasChildren() || (block.hasComponentSlots() && !block.isRoot())
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
	if (block.editInFragmentMode()) {
		const parentBlock = block.getParentBlock()
		canvasStore.editOnCanvas(
			block,
			(newBlock: Block) => parentBlock?.replaceChild(block, newBlock),
			`Save ${block.componentName}`,
		)
	} else {
		canvasStore.activeCanvas?.selectBlock(block, e, false)
	}
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
					let parentBlock = block.getParentBlock()
					// open all parent blocks and slots
					while (parentBlock && !parentBlock.isRoot()) {
						let slotName = parentBlock.parentSlotName
						expandedLayers.value.add(parentBlock?.componentId)
						parentBlock = parentBlock.getParentBlock()
						if (slotName) {
							const slotId = parentBlock?.getSlot(slotName)?.slotId
							if (slotId) {
								expandedSlots.value.add(slotId)
							}
						}
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
})
</script>
