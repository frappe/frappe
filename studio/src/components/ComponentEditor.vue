<template>
	<div
		class="editor pointer-events-none fixed z-[18] box-content select-none ring-2 ring-inset"
		ref="editor"
		:selected="isBlockSelected"
		:data-component-id="block.componentId"
		:class="getStyleClasses"
	></div>
</template>

<script setup>
import { inject, ref, computed, onMounted } from "vue"
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

const canvasProps = inject("canvasProps")
const store = useStore()
const editor = ref(null)
const updateTracker = ref(() => {})

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

onMounted(() => {
	updateTracker.value = trackTarget(props.target, editor.value, canvasProps)
})
</script>
