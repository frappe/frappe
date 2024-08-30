<template>
	<div>
		<Draggable
			class="component-tree"
			:model-value="blocks"
			item-key="componentId"
			:group="{ name: 'component-tree' }"
		>
			<template #item="{ element }">
				<div
					:data-component-layer-id="element.componentId"
					:title="element.componentId"
					class="dark:bg-zinc-900 min-w-24 cursor-pointer overflow-hidden rounded border border-transparent bg-white bg-opacity-50 text-base text-gray-700 dark:text-gray-500"
					@click.stop="store.selectBlock(element, $event, false)"
					@mouseover.stop="store.hoveredBlock = element.componentId"
					@mouseleave="store.hoveredBlock = null"
				>
					<span
						class="group my-[7px] flex items-center gap-1.5 pr-[2px] font-medium"
						:style="{ paddingLeft: `${indent}px` }"
						:class="{
							'!opacity-50': !element.isVisible(),
						}"
					>
						<FeatherIcon
							v-if="element.children && element.children.length && !element.isRoot()"
							:name="isExpanded(element) ? 'chevron-down' : 'chevron-right'"
							class="h-3 w-3"
							@click.stop="toggleExpanded(element)"
						/>
						<LucideIcon :name="element.getIcon()" class="h-3 w-3" />

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
						<span
							v-if="element.isRoot()"
							class="dark:text-zinc-500 ml-auto mr-2 text-sm capitalize text-gray-500"
						>
							{{ store.activeBreakpoint }}
						</span>
					</span>
					<div v-show="canShowChildLayer(element)">
						<ComponentLayers :blocks="element.children" ref="childLayer" :indent="childIndent" />
					</div>
				</div>
			</template>
		</Draggable>
	</div>
</template>

<script setup lang="ts">
import { PropType, ref } from "vue"
import { FeatherIcon } from "frappe-ui"
import Draggable from "vuedraggable"

import ComponentLayers from "@/components/ComponentLayers.vue"

import useStore from "@/store"
import Block from "@/utils/block"
import LucideIcon from "./LucideIcon.vue"

const props = defineProps({
	blocks: {
		type: Array as PropType<Block[]>,
		default: () => [],
	},
	indent: {
		type: Number,
		default: 10,
	},
})

const store = useStore()
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
</script>
