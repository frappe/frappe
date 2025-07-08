<!-- Extracted from Builder -->
<template>
	<span
		class="resize-dimensions absolute bottom-[-40px] right-[-40px] flex h-8 w-20 items-center justify-center whitespace-nowrap rounded-full bg-gray-600 p-2 text-sm text-white opacity-80"
		v-if="resizing"
	>
		{{ targetWidth }} x
		{{ targetHeight }}
	</span>

	<div
		class="left-handle ew-resize pointer-events-auto absolute bottom-0 left-[-2px] top-0 w-2 border-none bg-transparent"
	/>
	<div
		class="right-handle pointer-events-auto absolute bottom-0 right-[-2px] top-0 w-2 border-none bg-transparent"
		:class="{ 'cursor-ew-resize': true }"
		@mousedown.stop="handleRightResize"
	/>
	<div
		class="top-handle ns-resize pointer-events-auto absolute left-0 right-0 top-[-2px] h-2 border-none bg-transparent"
	/>
	<div
		class="bottom-handle pointer-events-auto absolute bottom-[-2px] left-0 right-0 h-2 border-none bg-transparent"
		:class="{ 'cursor-ns-resize': true }"
		@mousedown.stop="handleBottomResize"
	/>
	<div
		class="pointer-events-auto absolute bottom-[-5px] right-[-5px] h-[12px] w-[12px] cursor-nwse-resize rounded-full border-[2.5px] border-blue-400 bg-white"
		v-show="!resizing"
		@mousedown.stop="handleBottomCornerResize"
	/>
</template>

<script setup lang="ts">
import { pxToNumber } from "@/utils/helpers"
import { computed, onMounted, ref, watch, inject } from "vue"
import Block from "@/utils/block"
import guidesTracker from "@/utils/guidesTracker"
import useCanvasStore from "@/stores/canvasStore"

import type { CanvasProps } from "@/types/StudioCanvas"

const props = defineProps({
	targetBlock: {
		type: Block,
		default: null,
	},
	target: {
		type: [HTMLElement, SVGElement],
		default: null,
	},
})

const canvasProps = inject("canvasProps") as CanvasProps

let guides = null as unknown as ReturnType<typeof guidesTracker>
onMounted(() => {
	guides = guidesTracker(props.target as HTMLElement, canvasProps)
})

const resizing = ref(false)
const emit = defineEmits(["resizing"])
const canvasStore = useCanvasStore()

watch(resizing, () => {
	if (resizing.value) {
		if (canvasStore.activeCanvas) {
			canvasStore.activeCanvas.history?.pause()
		}
		emit("resizing", true)
	} else {
		if (canvasStore.activeCanvas) {
			canvasStore.activeCanvas?.history?.resume(undefined, true, true)
		}
		emit("resizing", false)
	}
})

const targetWidth = computed(() => {
	props.targetBlock.getStyle("width") // to trigger reactivity
	return Math.round(pxToNumber(getComputedStyle(props.target).getPropertyValue("width")))
})

const targetHeight = computed(() => {
	props.targetBlock.getStyle("height") // to trigger reactivity
	return Math.round(pxToNumber(getComputedStyle(props.target).getPropertyValue("height")))
})

const fontSize = computed(() => {
	props.targetBlock.getStyle("fontSize") // to trigger reactivity
	return Math.round(pxToNumber(getComputedStyle(props.target).getPropertyValue("font-size")))
})

const handleRightResize = (ev: MouseEvent) => {
	const startX = ev.clientX
	const startHeight = (props.target as HTMLElement).offsetHeight
	const startWidth = (props.target as HTMLElement).offsetWidth
	const blockStartWidth = props.targetBlock.getStyle("width") as string
	const blockStartHeight = props.targetBlock.getStyle("height") as string
	const startFontSize = fontSize.value || 0

	// to disable cursor jitter
	const docCursor = document.body.style.cursor
	document.body.style.cursor = window.getComputedStyle(ev.target as HTMLElement).cursor
	resizing.value = true
	guides.showX()
	const mousemove = (mouseMoveEvent: MouseEvent) => {
		const movement = (mouseMoveEvent.clientX - startX) / canvasProps.scale
		setWidth(movement, startWidth, blockStartWidth)
		if (mouseMoveEvent.shiftKey) {
			setHeight(movement, startHeight, blockStartHeight)
		}
		mouseMoveEvent.preventDefault()
	}
	document.addEventListener("mousemove", mousemove)
	document.addEventListener(
		"mouseup",
		(mouseUpEvent) => {
			document.body.style.cursor = docCursor
			document.removeEventListener("mousemove", mousemove)
			mouseUpEvent.preventDefault()
			resizing.value = false
			guides.hideX()
		},
		{ once: true },
	)
}

const handleBottomResize = (ev: MouseEvent) => {
	const startY = ev.clientY
	const startHeight = (props.target as HTMLElement).offsetHeight
	const startWidth = (props.target as HTMLElement).offsetWidth
	const blockStartWidth = props.targetBlock.getStyle("width") as string
	const blockStartHeight = props.targetBlock.getStyle("height") as string
	const startFontSize = fontSize.value || 0

	// to disable cursor jitter
	const docCursor = document.body.style.cursor
	document.body.style.cursor = window.getComputedStyle(ev.target as HTMLElement).cursor
	resizing.value = true
	guides.showY()

	const mousemove = (mouseMoveEvent: MouseEvent) => {
		const movement = (mouseMoveEvent.clientY - startY) / canvasProps.scale
		setHeight(movement, startHeight, blockStartHeight)
		if (mouseMoveEvent.shiftKey) {
			setWidth(movement, startWidth, blockStartWidth)
		}
		mouseMoveEvent.preventDefault()
	}
	document.addEventListener("mousemove", mousemove)
	document.addEventListener(
		"mouseup",
		(mouseUpEvent) => {
			document.body.style.cursor = docCursor
			document.removeEventListener("mousemove", mousemove)
			mouseUpEvent.preventDefault()
			resizing.value = false
			guides.hideY()
		},
		{ once: true },
	)
}

const handleBottomCornerResize = (ev: MouseEvent) => {
	const startX = ev.clientX
	const startY = ev.clientY
	const startHeight = (props.target as HTMLElement).offsetHeight
	const startWidth = (props.target as HTMLElement).offsetWidth
	const blockStartWidth = props.targetBlock.getStyle("width") as string
	const blockStartHeight = props.targetBlock.getStyle("height") as string
	const startFontSize = fontSize.value || 0

	// to disable cursor jitter
	const docCursor = document.body.style.cursor
	document.body.style.cursor = window.getComputedStyle(ev.target as HTMLElement).cursor
	resizing.value = true

	const mousemove = (mouseMoveEvent: MouseEvent) => {
		const movementX = (mouseMoveEvent.clientX - startX) / canvasProps.scale
		const movementY = (mouseMoveEvent.clientY - startY) / canvasProps.scale
		setWidth(movementX, startWidth, blockStartWidth)
		setHeight(mouseMoveEvent.shiftKey ? movementX : movementY, startHeight, blockStartHeight)
		mouseMoveEvent.preventDefault()
	}
	document.addEventListener("mousemove", mousemove)
	document.addEventListener(
		"mouseup",
		(mouseUpEvent) => {
			document.body.style.cursor = docCursor
			document.removeEventListener("mousemove", mousemove)
			mouseUpEvent.preventDefault()
			resizing.value = false
		},
		{ once: true },
	)
}

const setWidth = (movementX: number, startWidth: number, blockStartWidth: string) => {
	const finalWidth = Math.round(startWidth + movementX)
	if (blockStartWidth?.includes("%")) {
		const parentWidth = props.target.parentElement?.offsetWidth || 0
		const movementPercent = (movementX / parentWidth) * 100
		const startWidthPercent = (startWidth / parentWidth) * 100
		const finalWidthPercent = Math.abs(Math.round(startWidthPercent + movementPercent))
		props.targetBlock.setStyle("width", `${finalWidthPercent}%`)
	} else {
		props.targetBlock.setStyle("width", `${finalWidth}px`)
	}
}

const setHeight = (movementY: number, startHeight: number, blockStartHeight: string) => {
	const finalHeight = Math.round(startHeight + movementY)
	if (blockStartHeight?.includes("%")) {
		const parentHeight = props.target.parentElement?.offsetHeight || 0
		const movementPercent = (movementY / parentHeight) * 100
		const startHeightPercent = (startHeight / parentHeight) * 100
		const finalHeightPercent = Math.abs(Math.round(startHeightPercent + movementPercent))
		props.targetBlock.setStyle("height", `${finalHeightPercent}%`)
	} else {
		props.targetBlock.setStyle("height", `${finalHeight}px`)
	}
}
</script>
