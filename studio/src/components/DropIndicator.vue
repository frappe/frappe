<template>
	<div v-if="target.active" ref="rootEl" class="pointer-events-none fixed inset-0 z-[250]" :style="clipStyle">
		<!-- container outline only when moving into a DIFFERENT container, so an
		     in-place reorder stays quiet -->
		<div
			v-if="target.containerRect && !target.isSameContainer"
			class="absolute rounded ring-[1.5px] ring-inset"
			:class="containerClass"
			:style="containerStyle"
		/>

		<!-- insertion line: layout-aware (flex row/column, wrapped flex, grid) -->
		<div v-if="target.line" class="absolute rounded-full" :class="lineClass" :style="lineStyle">
			<span
				class="absolute h-[7px] w-[7px] -translate-x-1/2 -translate-y-1/2 rounded-full bg-inherit"
				:class="startCapClass"
			/>
			<span
				class="absolute h-[7px] w-[7px] -translate-x-1/2 -translate-y-1/2 rounded-full bg-inherit"
				:class="endCapClass"
			/>
		</div>
	</div>
</template>

<script setup lang="ts">
import { computed, ref } from "vue"
import useCanvasStore from "@/stores/canvasStore"

const LINE_WIDTH = 3

const canvasStore = useCanvasStore()
const target = computed(() => canvasStore.reorderTarget)
const rootEl = ref<HTMLElement>()

// Clip the full-viewport overlay to the canvas region so indicators never paint
// over the side panels. Recomputes on each drag update; the panels don't move mid-drag.
const clipStyle = computed(() => {
	if (!target.value.active) return {}
	const host = rootEl.value?.closest(".canvas-container") as HTMLElement | null
	if (!host) return {}
	const rect = host.getBoundingClientRect()
	const top = Math.max(0, rect.top)
	const left = Math.max(0, rect.left)
	const right = Math.max(0, window.innerWidth - rect.right)
	const bottom = Math.max(0, window.innerHeight - rect.bottom)
	return { clipPath: `inset(${top}px ${right}px ${bottom}px ${left}px)` }
})

const lineClass = computed(() => (target.value.isSlotTarget ? "bg-surface-purple-6" : "bg-surface-blue-6"))
const containerClass = computed(() =>
	target.value.isSlotTarget
		? "ring-outline-purple-4 bg-surface-purple-6/10"
		: "ring-outline-blue-4 bg-surface-blue-6/10",
)

const isVertical = computed(() => target.value.line?.orientation === "vertical")
const startCapClass = computed(() => (isVertical.value ? "left-1/2 top-0" : "left-0 top-1/2"))
const endCapClass = computed(() => (isVertical.value ? "left-1/2 top-full" : "left-full top-1/2"))

const containerStyle = computed(() => {
	const rect = target.value.containerRect
	if (!rect) return {}
	return {
		left: `${rect.left}px`,
		top: `${rect.top}px`,
		width: `${rect.width}px`,
		height: `${rect.height}px`,
	}
})

const lineStyle = computed(() => {
	const line = target.value.line
	if (!line) return { display: "none" }
	if (line.orientation === "vertical") {
		return {
			left: `${line.left - LINE_WIDTH / 2}px`,
			top: `${line.top}px`,
			width: `${LINE_WIDTH}px`,
			height: `${line.length}px`,
		}
	}
	return {
		left: `${line.left}px`,
		top: `${line.top - LINE_WIDTH / 2}px`,
		width: `${line.length}px`,
		height: `${LINE_WIDTH}px`,
	}
})
</script>
