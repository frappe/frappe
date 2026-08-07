<template>
	<div v-if="fragmentNodes.length" class="mt-5 flex w-full max-w-3xl flex-col gap-2 self-center">
		<span class="text-xs font-medium text-ink-gray-5">
			Fragments · {{ fragmentNodes.length }} - not rendered inline
		</span>
		<div
			v-for="block in fragmentNodes"
			:key="block.componentId"
			class="flex cursor-pointer items-center gap-3 rounded-lg border border-dashed bg-surface-base p-3"
			:class="block.isStudioComponent ? 'border-outline-purple-4' : 'border-outline-blue-4'"
			@click="editFragment(block)"
		>
			<div
				class="bg-surface-white flex h-7 w-7 shrink-0 items-center justify-center rounded"
				:class="block.isStudioComponent ? 'text-ink-purple-7' : 'text-ink-blue-6'"
			>
				<component :is="block.getIcon()" class="h-3.5 w-3.5" />
			</div>
			<div class="flex min-w-0 flex-1 flex-col">
				<span class="truncate text-sm font-medium leading-relaxed text-ink-gray-8">
					{{ block.getBlockDescription() }}
				</span>
				<span class="text-xs text-ink-gray-5">
					{{ getSubtitle(block) }}
				</span>
			</div>
			<span
				class="flex shrink-0 items-center gap-1 text-xs font-medium"
				:class="block.isStudioComponent ? 'text-ink-purple-6' : 'text-ink-blue-6'"
			>
				Edit
				<LucideArrowUpRight class="h-3 w-3" />
			</span>
		</div>
	</div>
</template>

<script setup lang="ts">
import { computed } from "vue"
import Block from "@/utils/block"
import useCanvasStore from "@/stores/canvasStore"
import useComponentStore from "@/stores/componentStore"
import useComponentEditorStore from "@/stores/componentEditorStore"
import LucidePenLine from "~icons/lucide/pen-line"
import LucideArrowUpRight from "~icons/lucide/arrow-up-right"

const props = defineProps<{
	rootBlock: Block
}>()

const canvasStore = useCanvasStore()
const componentStore = useComponentStore()
const componentEditorStore = useComponentEditorStore()

const fragmentNodes = computed(() => {
	const found: Block[] = []
	collectFragmentNodes(props.rootBlock, found)
	return found
})

// collect top-level collapsed fragment nodes — the primary fragment renders
// inline on the canvas, so it's skipped and traversed instead
function collectFragmentNodes(block: Block, found: Block[]) {
	block.getChildrenAndSlotContent().forEach((child) => {
		if (child.isFragmentNode() && child.componentId !== canvasStore.primaryFragmentId) {
			found.push(child)
		} else {
			collectFragmentNodes(child, found)
		}
	})
}

const getSubtitle = (block: Block) => {
	if (block.isStudioComponent) {
		const componentRoot = componentStore.componentMap.get(block.componentName)
		return `${componentRoot?.componentName || "Fragment"} · Studio Component`
	}
	return `${block.componentName} · Block`
}

const editFragment = (block: Block) => {
	if (block.isStudioComponent) {
		componentEditorStore.editComponent(block.componentName)
		return
	}
	const parentBlock = block.getParentBlock()
	canvasStore.editOnCanvas(
		block,
		(newBlock: Block) => parentBlock?.replaceChild(block, newBlock),
		`Save ${block.componentName}`,
	)
}
</script>
