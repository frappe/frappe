<template>
	<div ref="canvasContainer">
		<slot name="header"></slot>
		<div class="overlay absolute" id="overlay" ref="overlay" />
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

<script setup lang="ts">
import { ref, reactive, computed, onMounted, nextTick, provide } from "vue"
import { useDropZone, useElementBounding } from "@vueuse/core"
import { LoadingIndicator } from "frappe-ui"
import StudioComponent from "@/components/StudioComponent.vue"
import FitScreenIcon from "@/components/Icons/FitScreenIcon.vue"
import StudioCanvas from "@/components/StudioCanvas.vue"

import useStudioStore from "@/stores/studioStore"
import { getBlockCopy, getComponentBlock } from "@/utils/helpers"
import setPanAndZoom from "@/utils/panAndZoom"
import Block from "@/utils/block"

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
const canvas = ref<InstanceType<typeof StudioCanvas> | null>(null)
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

const rootComponent = ref(getBlockCopy(props.componentTree, true))

// handle dropping components
useDropZone(canvasContainer, {
	onDrop: (_files, ev) => {
		let { parentComponent, slotName } = getDropTarget(ev)
		const droppedComponentName = ev.dataTransfer?.getData("componentName")
		if (droppedComponentName && parentComponent) {
			const newBlock = getComponentBlock(droppedComponentName)
			if (slotName) {
				parentComponent.updateSlot(slotName, newBlock)
			} else {
				parentComponent.addChild(newBlock)
			}
		}
	},
	onOver: (_files, ev) => {
		const { parentComponent } = getDropTarget(ev)
		if (parentComponent) {
			store.hoveredBlock = parentComponent.componentId
		}
	},
})

const getDropTarget = (ev: DragEvent) => {
	let element = document.elementFromPoint(ev.x, ev.y) as HTMLElement
	let parentComponent = rootComponent.value
	let slotName

	if (element) {
		if (element.dataset.componentId) {
			parentComponent = findBlock(element.dataset.componentId) || parentComponent
			while (parentComponent && !parentComponent.canHaveChildren()) {
				parentComponent = parentComponent.getParentBlock()
			}
			slotName = element.dataset.slotName || store.selectedSlot?.slotName
		}
	}

	return {
		parentComponent,
		slotName,
	}
}

const findBlock = (componentId: string, blocks?: Block[]): Block | null => {
	if (!blocks) {
		blocks = [getRootBlock()]
	}

	for (const block of blocks) {
		if (block.componentId === componentId) return block

		if (block.children) {
			const found = findBlock(componentId, block.children)
			if (found) return found
		}

		if (block.componentSlots) {
			for (const slot of Object.values(block.componentSlots)) {
				if (Array.isArray(slot.slotContent)) {
					const found = findBlock(componentId, slot.slotContent)
					if (found) return found
				}
			}
		}
	}
	return null
}

const getRootBlock = () => rootComponent.value

const setRootBlock = (newBlock: Block, resetCanvas = false) => {
	rootComponent.value = newBlock
	if (resetCanvas) {
		nextTick(() => {
			setScaleAndTranslate()
		})
	}
}

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
	const canvasContainerEl = canvasContainer.value as unknown as HTMLElement
	const canvasEl = canvas.value as unknown as HTMLElement
	setPanAndZoom(canvasProps, canvasEl, canvasContainerEl)
	showBlocks.value = true
})

defineExpose({
	rootComponent,
	canvasProps,
	findBlock,
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
</style>
