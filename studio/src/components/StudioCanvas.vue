<template>
	<div ref="canvasContainer">
		<slot name="header"></slot>
		<div class="overlay absolute" id="overlay" ref="overlay" />
		<div
			v-if="isOverDropZone"
			class="pointer-events-none absolute bottom-0 left-0 right-0 top-0 z-30 bg-cyan-300 opacity-20"
		></div>
		<div
			class="fixed flex gap-40"
			ref="canvas"
			:style="{
				transformOrigin: 'top center',
				transform: `scale(${canvasProps.scale}) translate(${canvasProps.translateX}px, ${canvasProps.translateY}px)`,
			}"
		>
			<div class="dark:bg-zinc-900 absolute right-0 top-[-60px] flex rounded-md bg-white px-3">
				<div
					v-show="!canvasProps.scaling && !canvasProps.panning"
					class="w-auto cursor-pointer p-2"
					v-for="breakpoint in canvasProps.breakpoints"
					:key="breakpoint.device"
					@click.stop="breakpoint.visible = !breakpoint.visible"
				>
					<FeatherIcon
						:name="breakpoint.icon"
						class="h-8 w-6"
						:class="{
							'dark:text-zinc-50 text-gray-700': breakpoint.visible,
							'dark:text-zinc-500 text-gray-300': !breakpoint.visible,
						}"
					/>
				</div>
			</div>
			<div
				class="canvas relative flex h-full rounded-md bg-white shadow-2xl"
				:style="{
					...canvasStyles,
					background: canvasProps.background,
					width: `${breakpoint.width}px`,
				}"
				v-for="breakpoint in visibleBreakpoints"
				:key="breakpoint.device"
			>
				<div
					class="cursor dark:text-zinc-300 absolute left-0 select-none text-3xl text-gray-700"
					:style="{
						fontSize: `calc(${12}px * 1/${canvasProps.scale})`,
						top: `calc(${-20}px * 1/${canvasProps.scale})`,
					}"
					v-show="!canvasProps.scaling && !canvasProps.panning"
					@click="store.activeBreakpoint = breakpoint.device"
				>
					{{ breakpoint.displayName }}
				</div>
				<StudioComponent
					class="h-full min-h-[inherit]"
					v-if="showBlocks && rootComponent"
					:block="rootComponent"
					:breakpoint="breakpoint.device"
				/>
			</div>
		</div>

		<div
			class="dark:bg-zinc-900 dark:text-zinc-400 fixed bottom-12 left-[50%] z-40 flex translate-x-[-50%] cursor-default items-center justify-center gap-2 rounded-lg bg-white px-3 py-2 text-center text-sm font-semibold text-gray-600 shadow-md"
			v-show="!canvasProps.panning"
		>
			{{ Math.round(canvasProps.scale * 100) + "%" }}
			<div class="ml-2 cursor-pointer" @click="setScaleAndTranslate">
				<FitScreenIcon />
			</div>
		</div>
	</div>
</template>

<script setup>
import { ref, reactive, computed, onMounted, nextTick } from "vue"
import { useDropZone, useElementBounding } from "@vueuse/core"
import StudioComponent from "@/components/StudioComponent.vue"
import FitScreenIcon from "@/components/Icons/FitScreenIcon.vue"

import useStore from "@/store"
import { getBlockCopy, getComponentBlock } from "@/utils/helpers"
import setPanAndZoom from "@/utils/panAndZoom"

const props = defineProps({
	componentTree: {
		type: Object,
		required: true,
	},
	canvasStyles: {
		type: Object,
		default: () => ({}),
	},
})
const store = useStore()

const canvasContainer = ref(null)
const canvas = ref(null)
const overlay = ref(null)
const showBlocks = ref(false)

const canvasProps = reactive({
	overlayElement: null,
	background: "#fff",
	scale: 1,
	translateX: 0,
	translateY: 0,
	settingCanvas: true,
	scaling: false,
	panning: false,
	breakpoints: [
		{
			icon: "monitor",
			device: "desktop",
			displayName: "Desktop",
			width: 1400,
			visible: true,
		},
		{
			icon: "tablet",
			device: "tablet",
			displayName: "Tablet",
			width: 800,
			visible: false,
		},
		{
			icon: "smartphone",
			device: "mobile",
			displayName: "Mobile",
			width: 420,
			visible: false,
		},
	],
})

const visibleBreakpoints = computed(() => {
	return canvasProps.breakpoints.filter((breakpoint) => breakpoint.visible || breakpoint.device === "desktop")
})

const rootComponent = ref(getBlockCopy(props.componentTree, true))

// handle dropping components
const { isOverDropZone } = useDropZone(canvasContainer, {
	onDrop: (_files, ev) => {
		let element = document.elementFromPoint(ev.x, ev.y)
		let parentComponent = rootComponent.value

		if (element) {
			if (element.dataset.componentId) {
				parentComponent = findBlock(element.dataset.componentId) || parentComponent
			}
		}

		const componentName = ev.dataTransfer?.getData("componentName")
		if (componentName) {
			const newBlock = getComponentBlock(componentName)
			parentComponent.addChild(newBlock)
		}
	},
})

const findBlock = (componentId, blocks = null) => {
	if (!blocks) {
		blocks = [getRootBlock()]
	}

	for (const block of blocks) {
		if (block.componentId === componentId) return block

		if (block.children) {
			const found = findBlock(componentId, block.children)
			if (found) return found
		}
	}
}

const getRootBlock = () => rootComponent.value

// canvas positioning
const containerBound = reactive(useElementBounding(canvasContainer))
const canvasBound = reactive(useElementBounding(canvas))

const setScaleAndTranslate = async () => {
	if (document.readyState !== "complete") {
		await new Promise((resolve) => {
			window.addEventListener("load", resolve)
		})
	}
	const paddingX = 300
	const paddingY = 200

	await nextTick()
	canvasBound.update()
	const containerWidth = containerBound.width
	const canvasWidth = canvasBound.width / canvasProps.scale

	canvasProps.scale = containerWidth / (canvasWidth + paddingX * 2)

	canvasProps.translateX = 0
	canvasProps.translateY = 0
	await nextTick()
	const scale = canvasProps.scale
	canvasBound.update()
	const diffY = containerBound.top - canvasBound.top + paddingY * scale
	if (diffY !== 0) {
		canvasProps.translateY = diffY / scale
	}
	canvasProps.settingCanvas = false
}

onMounted(() => {
	canvasProps.overlayElement = overlay.value
	setScaleAndTranslate()
	const canvasContainerEl = canvasContainer.value
	const canvasEl = canvas.value
	setPanAndZoom(canvasProps, canvasEl, canvasContainerEl)
	showBlocks.value = true
})

defineExpose({
	canvasProps,
	findBlock,
	getRootBlock,
})
</script>

<style>
.hovered-block {
	@apply border-blue-300 text-gray-700 dark:border-blue-900 dark:text-gray-500;
}
.block-selected {
	@apply border-blue-400 text-gray-900 dark:border-blue-700 dark:text-gray-200;
}
</style>
