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
			<PaddingHandler
				:data-block-id="block.blockId"
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

<script setup>
import { ref, computed, onMounted } from "vue"

import ComponentContextMenu from "@/components/ComponentContextMenu.vue"
import BoxResizer from "@/components/BoxResizer.vue"
import PaddingHandler from "@/components/PaddingHandler.vue"
import MarginHandler from "@/components/MarginHandler.vue"

import Block from "@/utils/block"
import useStore from "@/store"
import trackTarget from "@/utils/trackTarget"

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

const store = useStore()
const editor = ref(null)
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
const handleClick = (ev) => {
	if (props.editable) return
	if (preventCLick.value) {
		preventCLick.value = false
		return
	}
	const editorWrapper = editor.value
	editorWrapper.classList.add("pointer-events-none")
	let element = document.elementFromPoint(ev.x, ev.y)
	if (element.classList.contains("editor")) {
		element.classList.remove("pointer-events-auto")
		element.classList.add("pointer-events-none")
		element = document.elementFromPoint(ev.x, ev.y)
	}
	if (element.classList.contains("__studio_component__")) {
		element.dispatchEvent(new MouseEvent("click", ev))
	}
}

onMounted(() => {
	updateTracker.value = trackTarget(props.target, editor.value, store.canvas.canvasProps)
})

defineExpose({
	element: editor,
})
</script>
