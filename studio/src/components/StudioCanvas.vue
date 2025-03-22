<template>
	<div ref="canvasContainer">
		<slot name="header"></slot>
		<div
			class="overlay absolute"
			:class="{ 'pointer-events-none': isOverDropZone }"
			id="overlay"
			ref="overlay"
		/>
		<Transition name="fade">
			<div
				class="absolute bottom-0 left-0 right-0 top-0 z-[19] grid w-full place-items-center bg-gray-50"
				v-show="store.settingPage"
			>
				<LoadingIndicator class="h-5 w-5 text-gray-700" />
			</div>
		</Transition>

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
				class="canvas relative flex h-full rounded-md bg-white shadow-2xl contain-layout"
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
					:key="rootComponent.componentId"
					:breakpoint="breakpoint.device"
				/>
			</div>
		</div>

		<div
			class="fixed bottom-12 left-[50%] z-40 flex translate-x-[-50%] cursor-default items-center justify-center gap-2 rounded-lg bg-white px-3 py-2 text-center text-sm font-semibold text-gray-600 shadow-md"
			v-show="!canvasProps.panning"
		>
			{{ Math.round(canvasProps.scale * 100) + "%" }}
			<div class="ml-2 cursor-pointer" @click="setScaleAndTranslate">
				<FitScreenIcon />
			</div>
		</div>
	</div>
</template>

<script setup lang="ts">
import { Ref, ref, watch, reactive, computed, onMounted, provide } from "vue"
import { LoadingIndicator } from "frappe-ui"
import StudioComponent from "@/components/StudioComponent.vue"
import FitScreenIcon from "@/components/Icons/FitScreenIcon.vue"

import useStudioStore from "@/stores/studioStore"
import { getBlockCopy } from "@/utils/helpers"
import setPanAndZoom from "@/utils/panAndZoom"
import Block from "@/utils/block"
import { useCanvasDropZone } from "@/utils/useCanvasDropZone"
import { useCanvasUtils } from "@/utils/useCanvasUtils"
import { CanvasHistory } from "@/types/StudioCanvas"

const props = defineProps({
	componentTree: {
		type: Block,
		required: true,
	},
	canvasStyles: {
		type: Object,
		default: () => ({}),
	},
})
const store = useStudioStore()

const canvasContainer = ref(null)
const canvas = ref<HTMLElement | null>(null)
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
provide("canvasProps", canvasProps)

const visibleBreakpoints = computed(() => {
	return canvasProps.breakpoints.filter((breakpoint) => breakpoint.visible || breakpoint.device === "desktop")
})
watch(
	() => canvasProps.breakpoints.map((b) => b.visible),
	() => {
		if (canvasProps.settingCanvas) {
			return
		}
		setScaleAndTranslate()
	},
)

// clone props.block into canvas data to avoid mutating them
const rootComponent = ref(getBlockCopy(props.componentTree, true))
const history = ref(null) as Ref<null> | CanvasHistory

const { setScaleAndTranslate, setupHistory, getRootBlock, setRootBlock, findBlock, removeBlock } =
	useCanvasUtils(canvasProps, canvasContainer, canvas, rootComponent, history)

const { isOverDropZone } = useCanvasDropZone(
	canvasContainer as unknown as Ref<HTMLElement>,
	rootComponent,
	findBlock,
)

onMounted(() => {
	const canvasContainerEl = canvasContainer.value as unknown as HTMLElement
	const canvasEl = canvas.value as unknown as HTMLElement
	canvasProps.overlayElement = overlay.value
	setScaleAndTranslate()
	showBlocks.value = true
	setupHistory()
	setPanAndZoom(canvasProps, canvasEl, canvasContainerEl)
})

defineExpose({
	history,
	rootComponent,
	canvasProps,
	findBlock,
	removeBlock,
	getRootBlock,
	setRootBlock,
})
</script>

<style>
.hovered-block {
	@apply border-blue-300 text-gray-700 dark:border-blue-900 dark:text-gray-500;
}
.block-selected {
	@apply border-blue-400 text-gray-900 dark:border-blue-700 dark:text-gray-200;
}
.slot-selected {
	@apply border-purple-400 text-gray-900;
}
#placeholder {
	@apply transition-all;
}
.vertical-placeholder {
	@apply mx-4 h-full min-h-5 w-auto border-l-2 border-dashed border-blue-500;
}
.horizontal-placeholder {
	@apply my-4 h-auto w-full border-t-2 border-dashed border-blue-500;
}
</style>
