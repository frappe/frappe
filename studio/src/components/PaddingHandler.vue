<!-- Extracted from Builder -->
<template>
	<div
		class="group"
		:class="{
			'opacity-40': !updating,
			'opacity-70': updating,
		}"
		@click.stop
	>
		<div
			class="padding-handler pointer-events-none absolute flex w-full bg-purple-400"
			:style="{
				height: topPaddingHandlerHeight + 'px',
			}"
			ref="topPaddingHandler"
		>
			<div
				class="pointer-events-auto absolute left-[50%] rounded-full border-2 border-purple-500 bg-purple-400 hover:scale-125"
				v-show="canvasProps.scale > 0.5"
				:style="{
					borderWidth: handleBorderWidth,
					bottom: topHandle.bottom,
					left: topHandle.left,
					height: topHandle.height + 'px',
					width: topHandle.width + 'px',
				}"
				:class="{
					'cursor-ns-resize': !disableHandlers,
					hidden: updating,
				}"
				@mousedown.stop="handlePadding($event, Position.Top)"
			/>
			<div class="m-auto text-sm text-purple-900" v-show="updating">
				{{ blockStyles.paddingTop }}
			</div>
		</div>
		<div
			class="padding-handler pointer-events-none absolute bottom-0 flex w-full bg-purple-400"
			:style="{
				height: bottomPaddingHandlerHeight + 'px',
			}"
			ref="bottomPaddingHandler"
		>
			<div
				class="pointer-events-auto absolute left-[50%] rounded-full border-2 border-purple-500 bg-purple-400 hover:scale-125"
				v-show="canvasProps.scale > 0.5"
				:style="{
					borderWidth: handleBorderWidth,
					top: bottomHandle.top,
					left: bottomHandle.left,
					height: bottomHandle.height + 'px',
					width: bottomHandle.width + 'px',
				}"
				:class="{
					'cursor-ns-resize': !disableHandlers,
					hidden: updating,
				}"
				@mousedown.stop="handlePadding($event, Position.Bottom)"
			/>
			<div class="m-auto text-sm text-purple-900" v-show="updating">
				{{ blockStyles.paddingBottom }}
			</div>
		</div>
		<div
			class="padding-handler pointer-events-none absolute left-0 flex h-full bg-purple-400"
			:style="{
				width: leftPaddingHandlerWidth + 'px',
			}"
			ref="leftPaddingHandler"
		>
			<div
				class="pointer-events-auto absolute top-[50%] rounded-full border-2 border-purple-500 bg-purple-400 hover:scale-125"
				v-show="canvasProps.scale > 0.5"
				:style="{
					borderWidth: handleBorderWidth,
					right: leftHandle.right,
					top: leftHandle.top,
					height: leftHandle.height + 'px',
					width: leftHandle.width + 'px',
				}"
				:class="{
					'cursor-ew-resize': !disableHandlers,
					hidden: updating,
				}"
				@mousedown.stop="handlePadding($event, Position.Left)"
			/>
			<div class="m-auto text-sm text-purple-900" v-show="updating">
				{{ blockStyles.paddingLeft }}
			</div>
		</div>
		<div
			class="padding-handler pointer-events-none absolute right-0 flex h-full bg-purple-400"
			:style="{
				width: rightPaddingHandlerWidth + 'px',
			}"
			ref="rightPaddingHandler"
		>
			<div
				class="pointer-events-auto absolute top-[50%] rounded-full border-2 border-purple-500 bg-purple-400 hover:scale-125"
				v-show="canvasProps.scale > 0.5"
				:style="{
					borderWidth: handleBorderWidth,
					left: rightHandle.left,
					top: rightHandle.top,
					height: rightHandle.height + 'px',
					width: rightHandle.width + 'px',
				}"
				:class="{
					'cursor-ew-resize': !disableHandlers,
					hidden: updating,
				}"
				@mousedown.stop="handlePadding($event, Position.Right)"
			/>
			<div class="m-auto text-sm text-purple-900" v-show="updating">
				{{ blockStyles.paddingRight }}
			</div>
		</div>
	</div>
</template>
<script setup lang="ts">
import { clamp } from "@vueuse/core"
import { computed, inject, ref, watchEffect } from "vue"
import Block from "../utils/block"
import { pxToNumber } from "../utils/helpers"

import type { CanvasProps } from "@/types/StudioCanvas"

const canvasProps = inject("canvasProps") as CanvasProps

const props = defineProps({
	targetBlock: {
		type: Block,
		required: true,
	},
	disableHandlers: {
		type: Boolean,
		default: false,
	},
	onUpdate: {
		type: Function,
		default: null,
	},
	breakpoint: {
		type: String,
		default: "desktop",
	},
	target: {
		type: [HTMLElement, SVGElement],
		required: true,
	},
})

const updating = ref(false)
const emit = defineEmits(["update"])

watchEffect(() => {
	emit("update", updating.value)
})

const blockStyles = computed(() => {
	let styleObj = props.targetBlock.baseStyles
	if (props.breakpoint === "mobile") {
		styleObj = { ...styleObj, ...props.targetBlock.mobileStyles }
	} else if (props.breakpoint === "tablet") {
		styleObj = { ...styleObj, ...props.targetBlock.tabletStyles }
	}
	return styleObj
})

const topPaddingHandlerHeight = computed(() => {
	return getPadding("Top")
})

const bottomPaddingHandlerHeight = computed(() => {
	return getPadding("Bottom")
})

const leftPaddingHandlerWidth = computed(() => {
	return getPadding("Left")
})

const rightPaddingHandlerWidth = computed(() => {
	return getPadding("Right")
})

const getPadding = (side: "Top" | "Left" | "Right" | "Bottom") => {
	blockStyles.value.paddingRight
	blockStyles.value.paddingTop
	blockStyles.value.paddingBottom
	blockStyles.value.paddingLeft
	blockStyles.value.padding
	return pxToNumber(getComputedStyle(props.target)[`padding${side}`]) * canvasProps.scale
}

const handleBorderWidth = computed(() => {
	return `${clamp(1 * canvasProps.scale, 1, 2)}px`
})

const topHandle = computed(() => {
	const width = clamp(16 * canvasProps.scale, 8, 32)
	const height = clamp(4 * canvasProps.scale, 2, 8)
	return {
		width: width,
		height: height,
		bottom: `clamp(-20px, calc(-6px * ${canvasProps.scale}), -8px)`,
		left: `calc(50% - ${width / 2}px)`,
	}
})

const bottomHandle = computed(() => {
	const width = clamp(16 * canvasProps.scale, 8, 32)
	const height = clamp(4 * canvasProps.scale, 2, 8)
	return {
		width: width,
		height: height,
		top: `clamp(-20px, calc(-6px * ${canvasProps.scale}), -8px)`,
		left: `calc(50% - ${width / 2}px)`,
	}
})

const leftHandle = computed(() => {
	const width = clamp(4 * canvasProps.scale, 2, 8)
	const height = clamp(16 * canvasProps.scale, 8, 32)
	return {
		width: width,
		height: height,
		right: `clamp(-20px, calc(-6px * ${canvasProps.scale}), -8px)`,
		top: `calc(50% - ${height / 2}px)`,
	}
})

const rightHandle = computed(() => {
	const width = clamp(4 * canvasProps.scale, 2, 8)
	const height = clamp(16 * canvasProps.scale, 8, 32)
	return {
		width: width,
		height: height,
		left: `clamp(-20px, calc(-6px * ${canvasProps.scale}), -8px)`,
		top: `calc(50% - ${height / 2}px)`,
	}
})

enum Position {
	Top = "top",
	Right = "right",
	Bottom = "bottom",
	Left = "left",
}

const messageShown = ref(false)

const handlePadding = (ev: MouseEvent, position: Position) => {
	if (props.disableHandlers) return
	updating.value = true
	const startY = ev.clientY
	const startX = ev.clientX
	const target = ev.target as HTMLElement

	const startTop = pxToNumber(blockStyles.value.paddingTop) || 5
	const startBottom = pxToNumber(blockStyles.value.paddingBottom) || 5
	const startLeft = pxToNumber(blockStyles.value.paddingLeft) || 5
	const startRight = pxToNumber(blockStyles.value.paddingRight) || 5

	// to disable cursor jitter
	const docCursor = document.body.style.cursor
	document.body.style.cursor = window.getComputedStyle(target).cursor

	const mousemove = (mouseMoveEvent: MouseEvent) => {
		let movement = 0
		let affectingAxis = null
		props.onUpdate && props.onUpdate()
		if (position === Position.Top) {
			movement = Math.max(startTop + mouseMoveEvent.clientY - startY, 0)
			props.targetBlock.setStyle("paddingTop", movement + "px")
			affectingAxis = "y"
		} else if (position === Position.Bottom) {
			movement = Math.max(startBottom + startY - mouseMoveEvent.clientY, 0)
			props.targetBlock.setStyle("paddingBottom", movement + "px")
			affectingAxis = "y"
		} else if (position === Position.Left) {
			movement = Math.max(startLeft + mouseMoveEvent.clientX - startX, 0)
			props.targetBlock.setStyle("paddingLeft", movement + "px")
			affectingAxis = "x"
		} else if (position === Position.Right) {
			movement = Math.max(startRight + startX - mouseMoveEvent.clientX, 0)
			props.targetBlock.setStyle("paddingRight", movement + "px")
			affectingAxis = "x"
		}

		if (mouseMoveEvent.altKey) {
			if (affectingAxis === "y") {
				props.targetBlock.setStyle("paddingTop", movement + "px")
				props.targetBlock.setStyle("paddingBottom", movement + "px")
			} else if (affectingAxis === "x") {
				props.targetBlock.setStyle("paddingLeft", movement + "px")
				props.targetBlock.setStyle("paddingRight", movement + "px")
			}
		} else if (mouseMoveEvent.shiftKey) {
			props.targetBlock.setStyle("paddingTop", movement + "px")
			props.targetBlock.setStyle("paddingBottom", movement + "px")
			props.targetBlock.setStyle("paddingLeft", movement + "px")
			props.targetBlock.setStyle("paddingRight", movement + "px")
		}

		mouseMoveEvent.preventDefault()
		mouseMoveEvent.stopPropagation()
	}
	document.addEventListener("mousemove", mousemove)
	document.addEventListener(
		"mouseup",
		(mouseUpEvent) => {
			document.body.style.cursor = docCursor
			document.removeEventListener("mousemove", mousemove)
			updating.value = false
			mouseUpEvent.preventDefault()
		},
		{ once: true },
	)
}
</script>
