<template>
	<ComponentContextMenu :block="block" :editable="false" v-slot="{ onContextMenu }">
		<div
			class="editor pointer-events-none fixed z-[18] box-content select-none ring-2 ring-inset"
			ref="editor"
			:selected="isBlockSelected"
			:data-component-id="block.componentId"
			:class="getStyleClasses"
			@contextmenu="onContextMenu"
			@click.stop="handleClick"
		>
			<!-- Component name label -->
			<span
				v-if="!props.block.isRoot()"
				class="absolute -top-3 left-0 inline-block text-xs"
				:class="isBlockSelected ? 'bg-blue-500 text-white' : 'text-blue-500'"
			>
				{{ block.componentName }}
			</span>

			<PaddingHandler
				:data-block-id="block.componentId"
				v-if="showMarginPaddingHandlers"
				:target-block="block"
				:target="target"
				:on-update="updateTracker"
				:disable-handlers="false"
				:breakpoint="breakpoint"
			/>
			<MarginHandler
				v-if="showMarginPaddingHandlers"
				:target-block="block"
				:target="target"
				:on-update="updateTracker"
				:disable-handlers="false"
				:breakpoint="breakpoint"
			/>
			<BoxResizer v-if="showResizer" :targetBlock="block" @resizing="resizing = $event" :target="target" />
		</div>
	</ComponentContextMenu>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, Ref, watchEffect, nextTick } from "vue"

import ComponentContextMenu from "@/components/ComponentContextMenu.vue"
import BoxResizer from "@/components/BoxResizer.vue"
import PaddingHandler from "@/components/PaddingHandler.vue"
import MarginHandler from "@/components/MarginHandler.vue"

import Block from "@/utils/block"
import useStudioStore from "@/stores/studioStore"
import trackTarget from "@/utils/trackTarget"

import { CanvasProps } from "@/types"

const props = defineProps({
	block: {
		type: Block,
		required: true,
	},
	breakpoint: {
		type: String,
		default: "desktop",
	},
	target: {
		type: [HTMLElement, SVGElement],
		required: true,
	},
	isSelected: {
		type: Boolean,
		default: false,
	},
})

const store = useStudioStore()
const editor = ref(null) as unknown as Ref<HTMLElement>
const resizing = ref(false)
const updateTracker = ref(() => {})

const showMarginPaddingHandlers = computed(() => {
	return isBlockSelected.value && !props.block.isRoot() && !resizing.value
})

const showResizer = computed(() => {
	return !props.block.isRoot() && isBlockSelected.value
})

const isBlockSelected = computed(() => {
	return props.isSelected && props.breakpoint === store.activeBreakpoint
})

const getStyleClasses = computed(() => {
	const classes = ["ring-blue-400"]

	if (isBlockSelected.value && !props.block.isRoot()) {
		// make editor interactive
		classes.push("pointer-events-auto")
		// Place the block on the top of the stack
		classes.push("!z-[19]")
	}
	return classes
})

const preventCLick = ref(false)
const handleClick = (ev: MouseEvent) => {
	if (preventCLick.value) {
		preventCLick.value = false
		return
	}
	const editorWrapper = editor.value
	editorWrapper.classList.add("pointer-events-none")
	let element = document.elementFromPoint(ev.x, ev.y) as HTMLElement
	if (element.classList.contains("editor")) {
		element.classList.remove("pointer-events-auto")
		element.classList.add("pointer-events-none")
		element = document.elementFromPoint(ev.x, ev.y) as HTMLElement
	}
	if (element.classList.contains("__studio_component__")) {
		element.dispatchEvent(new MouseEvent("click", ev))
	}
}

watchEffect(() => {
	const parentBlock = props.block.getParentBlock()
	// on rearranging blocks
	parentBlock?.getChildIndex(props.block)

	// on changing panel states
	store.studioLayout.leftPanelWidth
	store.studioLayout.rightPanelWidth
	store.studioLayout.showLeftPanel
	store.studioLayout.showRightPanel

	store.activeBreakpoint
	store.canvas?.canvasProps.breakpoints.map((breakpoint) => breakpoint.visible)

	nextTick(() => {
		updateTracker.value()
	})
})

onMounted(() => {
	updateTracker.value = trackTarget(props.target, editor.value, store.canvas?.canvasProps as CanvasProps)
})

defineExpose({
	element: editor,
})
</script>
