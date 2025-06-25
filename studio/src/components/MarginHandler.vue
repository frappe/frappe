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
			class="margin-handler pointer-events-none absolute flex w-full bg-yellow-200"
			:style="{
				height: topMarginHandlerHeight + 'px',
				top: `calc(0% - ${topMarginHandlerHeight}px)`,
			}"
			ref="topMarginHandler"
		>
			<div
				class="pointer-events-auto absolute left-[50%] rounded-full border-2 border-yellow-800 bg-yellow-400 hover:scale-125"
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
				@mousedown.stop="handleMargin($event, Position.Top)"
			/>
			<div class="m-auto text-sm text-yellow-900" v-show="updating">
				{{ blockStyles.marginTop || "auto" }}
			</div>
		</div>
		<div
			class="margin-handler pointer-events-none absolute bottom-0 flex w-full bg-yellow-200"
			:style="{
				height: bottomMarginHandlerHeight + 'px',
				bottom: `calc(0% - ${bottomMarginHandlerHeight}px)`,
			}"
			ref="bottomMarginHandler"
		>
			<div
				class="pointer-events-auto absolute left-[50%] rounded-full border-2 border-yellow-800 bg-yellow-400 hover:scale-125"
				v-show="canvasProps.scale > 0.5"
				:style="{
					borderWidth: handleBorderWidth,
					bottom: bottomHandle.bottom,
					left: bottomHandle.left,
					height: bottomHandle.height + 'px',
					width: bottomHandle.width + 'px',
				}"
				:class="{
					'cursor-ns-resize': !disableHandlers,
					hidden: updating,
				}"
				@mousedown.stop="handleMargin($event, Position.Bottom)"
			/>
			<div class="m-auto text-sm text-yellow-900" v-show="updating">
				{{ blockStyles.marginBottom || "auto" }}
			</div>
		</div>
		<div
			class="margin-handler pointer-events-none absolute left-0 flex h-full bg-yellow-200"
			:style="{
				width: leftMarginHandlerWidth + 'px',
				left: `calc(0% - ${leftMarginHandlerWidth}px)`,
			}"
			ref="leftMarginHandler"
		>
			<div
				class="pointer-events-auto absolute top-[50%] rounded-full border-2 border-yellow-800 bg-yellow-400 hover:scale-125"
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
				@mousedown.stop="handleMargin($event, Position.Left)"
			/>
			<div class="m-auto text-sm text-yellow-900" v-show="updating">
				{{ blockStyles.marginLeft || "auto" }}
			</div>
		</div>
		<div
			class="margin-handler pointer-events-none absolute right-0 flex h-full bg-yellow-200"
			:style="{
				width: rightMarginHandlerWidth + 'px',
				right: `calc(0% - ${rightMarginHandlerWidth}px)`,
			}"
			ref="rightMarginHandler"
		>
			<div
				class="pointer-events-auto absolute top-[50%] rounded-full border-2 border-yellow-800 bg-yellow-400 hover:scale-125"
				v-show="canvasProps.scale > 0.5"
				:style="{
					borderWidth: handleBorderWidth,
					right: rightHandle.right,
					top: rightHandle.top,
					height: rightHandle.height + 'px',
					width: rightHandle.width + 'px',
				}"
				:class="{
					'cursor-ew-resize': !disableHandlers,
					hidden: updating,
				}"
				@mousedown.stop="handleMargin($event, Position.Right)"
			/>
			<div class="m-auto text-sm text-yellow-900" v-show="updating">
				{{ blockStyles.marginRight || "auto" }}
			</div>
		</div>
	</div>
</template>

<script setup lang="ts">
import { clamp } from "@vueuse/core"
import { computed, inject, ref, watchEffect } from "vue"
import Block from "@/utils/block"
import { pxToNumber } from "@/utils/helpers"

import type { CanvasProps } from "@/types/StudioCanvas"

const props = defineProps({
	targetBlock: {
		type: Block,
		required: true,
	},
	target: {
		type: [HTMLElement, SVGElement],
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
})

const updating = ref(false)
const emit = defineEmits(["update"])

const canvasProps = inject("canvasProps") as CanvasProps

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

const topMarginHandlerHeight = computed(() => {
	blockStyles.value.marginTop
	blockStyles.value.display
	blockStyles.value.margin
	let marginTop = window.getComputedStyle(props.target).marginTop
	let value = pxToNumber(marginTop) * canvasProps.scale
	return value
})
const bottomMarginHandlerHeight = computed(() => {
	blockStyles.value.marginBottom
	blockStyles.value.display
	blockStyles.value.margin
	let marginBottom = window.getComputedStyle(props.target).marginBottom
	let value = pxToNumber(marginBottom) * canvasProps.scale
	return value
})
const leftMarginHandlerWidth = computed(() => {
	blockStyles.value.marginLeft
	blockStyles.value.display
	blockStyles.value.margin
	let marginLeft = window.getComputedStyle(props.target).marginLeft
	let value = pxToNumber(marginLeft) * canvasProps.scale
	return value
})
const rightMarginHandlerWidth = computed(() => {
	blockStyles.value.marginRight
	blockStyles.value.display
	blockStyles.value.margin
	let marginRight = window.getComputedStyle(props.target).marginRight
	let value = pxToNumber(marginRight) * canvasProps.scale
	return value
})

const handleBorderWidth = computed(() => {
	return `${clamp(1 * canvasProps.scale, 1, 2)}px`
})

const topHandle = computed(() => {
	const width = clamp(16 * canvasProps.scale, 8, 32)
	const height = clamp(4 * canvasProps.scale, 2, 8)
	return {
		width: width,
		height: height,
		bottom: `clamp(0px, calc(4px * ${canvasProps.scale}), 12px)`,
		left: `calc(50% - ${width / 2}px)`,
	}
})

const bottomHandle = computed(() => {
	const width = clamp(16 * canvasProps.scale, 8, 32)
	const height = clamp(4 * canvasProps.scale, 2, 8)
	return {
		width: width,
		height: height,
		bottom: `clamp(-16px, calc(-8px * ${canvasProps.scale}), 2px)`,
		left: `calc(50% - ${width / 2}px)`,
	}
})

const leftHandle = computed(() => {
	const width = clamp(4 * canvasProps.scale, 2, 8)
	const height = clamp(16 * canvasProps.scale, 8, 32)
	return {
		width: width,
		height: height,
		right: `clamp(0px, calc(4px * ${canvasProps.scale}), 12px)`,
		top: `calc(50% - ${height / 2}px)`,
	}
})

const rightHandle = computed(() => {
	const width = clamp(4 * canvasProps.scale, 2, 8)
	const height = clamp(16 * canvasProps.scale, 8, 32)
	return {
		width: width,
		height: height,
		right: `clamp(-16px, calc(-8px * ${canvasProps.scale}), 2px)`,
		top: `calc(50% - ${height / 2}px)`,
	}
})

enum Position {
	Top = "top",
	Right = "right",
	Bottom = "bottom",
	Left = "left",
}

const handleMargin = (ev: MouseEvent, position: Position) => {
	if (props.disableHandlers) return
	updating.value = true
	const startY = ev.clientY
	const startX = ev.clientX
	const target = ev.target as HTMLElement

	const startTop = pxToNumber(blockStyles.value.marginTop) || 0
	const startBottom = pxToNumber(blockStyles.value.marginBottom) || 0
	const startLeft = pxToNumber(blockStyles.value.marginLeft) || 0
	const startRight = pxToNumber(blockStyles.value.marginRight) || 0

	// to disable cursor jitter
	const docCursor = document.body.style.cursor
	document.body.style.cursor = window.getComputedStyle(target).cursor

	const mousemove = (mouseMoveEvent: MouseEvent) => {
		let movement = 0
		let affectingAxis = null
		props.onUpdate && props.onUpdate()
		if (position === Position.Top) {
			movement = Math.max(startTop + mouseMoveEvent.clientY - startY, 0)
			props.targetBlock.setStyle("marginTop", movement + "px")
			affectingAxis = "y"
		} else if (position === Position.Bottom) {
			movement = Math.max(startBottom + mouseMoveEvent.clientY - startY, 0)
			props.targetBlock.setStyle("marginBottom", movement + "px")
			affectingAxis = "y"
		} else if (position === Position.Left) {
			movement = Math.max(startLeft + mouseMoveEvent.clientX - startX, 0)
			props.targetBlock.setStyle("marginLeft", movement + "px")
			affectingAxis = "x"
		} else if (position === Position.Right) {
			movement = Math.max(startRight + mouseMoveEvent.clientX - startX, 0)
			props.targetBlock.setStyle("marginRight", movement + "px")
			affectingAxis = "x"
		}

		if (mouseMoveEvent.shiftKey) {
			props.targetBlock.setStyle("marginTop", movement + "px")
			props.targetBlock.setStyle("marginBottom", movement + "px")
			props.targetBlock.setStyle("marginLeft", movement + "px")
			props.targetBlock.setStyle("marginRight", movement + "px")
		} else if (mouseMoveEvent.altKey) {
			if (affectingAxis === "y") {
				props.targetBlock.setStyle("marginTop", movement + "px")
				props.targetBlock.setStyle("marginBottom", movement + "px")
			} else if (affectingAxis === "x") {
				props.targetBlock.setStyle("marginLeft", movement + "px")
				props.targetBlock.setStyle("marginRight", movement + "px")
			}
		}

		mouseMoveEvent.preventDefault()
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
