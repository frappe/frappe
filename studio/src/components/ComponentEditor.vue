<template>
	<div
		class="editor pointer-events-none fixed z-[18] box-content select-none ring-2 ring-inset"
		ref="editor"
		:selected="isBlockSelected"
		:data-component-id="block.componentId"
		:class="getStyleClasses"
		@click.stop="handleClick"
	>
		<!-- Component name label -->
		<span
			v-if="!props.block.isRoot() && isPrimaryInstance"
			class="absolute -top-3 left-0 inline-flex items-center gap-1 text-xs"
			:class="componentLabelClasses"
		>
			<LucideRepeat v-if="block.isRepeater() || block.isRepeated()" class="h-3 w-3 shrink-0" />
			{{ block.getBlockDescription() }}
			<template v-if="showEditComponentAction">
				<span class="mx-2 h-3 w-px bg-current opacity-30"></span>
				<button
					class="pointer-events-auto inline-flex cursor-pointer items-center gap-1 font-medium hover:opacity-80"
					title="Edit component"
					@click.stop="openComponentEditor"
				>
					<LucidePenLine class="h-2.5 w-2.5" />
					Edit
				</button>
			</template>
		</span>

		<PaddingHandler
			:data-block-id="block.componentId"
			v-if="showMarginPaddingHandlers"
			:target-block="block"
			:target="target"
			:on-update="tracker?.update"
			:disable-handlers="false"
			:breakpoint="breakpoint"
		/>
		<MarginHandler
			v-if="showMarginPaddingHandlers"
			:target-block="block"
			:target="target"
			:on-update="tracker?.update"
			:disable-handlers="false"
			:breakpoint="breakpoint"
		/>
		<BoxResizer v-if="showResizer" :targetBlock="block" @resizing="resizing = $event" :target="target" />

		<!-- Slot Overlays -->
		<template v-if="showSlotOverlays" v-for="(slot, slotName) in block.componentSlots" :key="slotName">
			<div
				:ref="(el: any) => setSlotOverlayRefs(slotName, el)"
				:data-slot-name="slotName"
				:data-slot-id="slot.slotId"
				:data-component-id="block.componentId"
				class="pointer-events-none fixed ring-2 ring-inset ring-outline-purple-5"
				:class="isSlotSelected(slot.slotId) ? 'opacity-100' : 'opacity-65'"
				:style="{
					minWidth: `calc(${20}px * ${canvasProps.scale})`,
					minHeight: `calc(${20}px * ${canvasProps.scale})`,
				}"
			>
				<span
					class="absolute -top-3 left-0 inline-block text-nowrap text-xs text-ink-base"
					:class="isSlotSelected(slot.slotId) ? 'bg-surface-purple-6' : 'bg-surface-purple-6/65'"
				>
					#{{ slotName }}
				</span>
			</div>
		</template>
	</div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, Ref, watchEffect, nextTick, inject, watch } from "vue"
import BoxResizer from "@/components/BoxResizer.vue"
import PaddingHandler from "@/components/PaddingHandler.vue"
import MarginHandler from "@/components/MarginHandler.vue"
import LucideRepeat from "~icons/lucide/repeat"
import LucidePenLine from "~icons/lucide/pen-line"

import Block from "@/utils/block"
import useStudioStore from "@/stores/studioStore"
import useCanvasStore from "@/stores/canvasStore"
import useComponentEditorStore from "@/stores/componentEditorStore"
import trackTarget, { Tracker } from "@/utils/trackTarget"

import type { CanvasProps } from "@/types/StudioCanvas"

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
	isPrimaryInstance: {
		type: Boolean,
		default: true,
	},
})

const store = useStudioStore()
const canvasStore = useCanvasStore()
const editor = ref(null) as unknown as Ref<HTMLElement>
const resizing = ref(false)
const tracker = ref<Tracker>()

const canvasProps = inject("canvasProps") as CanvasProps

const showMarginPaddingHandlers = computed(() => {
	return (
		props.isPrimaryInstance &&
		isBlockSelected.value &&
		!props.block.isRoot() &&
		!resizing.value &&
		!canvasStore.isDragging
	)
})

const showResizer = computed(() => {
	return (
		props.isPrimaryInstance &&
		!props.block.isRoot() &&
		isBlockSelected.value &&
		!canvasStore.isDragging &&
		!props.block.getParentBlock()?.isGrid() &&
		!(props.block.isHTML() && !props.block.isSVG() && !props.block.isIframe())
	)
})

const isBlockSelected = computed(() => {
	return props.isSelected && props.breakpoint === canvasStore.activeCanvas?.activeBreakpoint
})

const isSlotSelected = (slotId: string) => {
	return canvasStore.activeCanvas?.selectedSlot?.slotId === slotId
}

const getStyleClasses = computed(() => {
	const classes = []

	if (props.block.isStudioComponent) {
		classes.push("ring-outline-purple-4")
	} else {
		classes.push("ring-outline-blue-4")
	}

	if (!props.isPrimaryInstance) {
		classes.push("opacity-40")
		return classes
	}

	if (isBlockSelected.value && !props.block.isRoot() && !canvasStore.isDragging) {
		// make editor interactive
		classes.push("pointer-events-auto")
		// Place the block on the top of the stack
		classes.push("!z-[19]")
	}
	return classes
})

const showEditComponentAction = computed(() => {
	return isBlockSelected.value && props.block.isStudioComponent && !canvasStore.isDragging
})

const openComponentEditor = () => {
	useComponentEditorStore().editComponent(props.block.componentName)
}

const componentLabelClasses = computed(() => {
	if (isBlockSelected.value) {
		return props.block.isStudioComponent
			? "bg-surface-purple-6 text-ink-base"
			: "bg-surface-blue-6 text-ink-base"
	} else {
		return props.block.isStudioComponent ? "text-ink-purple-6" : "text-ink-blue-6"
	}
})

const preventClick = ref(false)
const handleClick = (ev: MouseEvent) => {
	if (preventClick.value) {
		preventClick.value = false
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
	props.block.getStyle("top")
	props.block.getStyle("left")
	props.block.getStyle("bottom")
	props.block.getStyle("right")
	props.block.getStyle("position")

	const parentBlock = props.block.getParentBlock()
	// on rearranging blocks
	parentBlock?.getChildIndex(props.block)
	parentBlock?.getStyle("display")
	parentBlock?.getStyle("justifyContent")
	parentBlock?.getStyle("alignItems")
	parentBlock?.getStyle("flexDirection")
	parentBlock?.getStyle("paddingTop")
	parentBlock?.getStyle("paddingBottom")
	parentBlock?.getStyle("paddingLeft")
	parentBlock?.getStyle("paddingRight")
	parentBlock?.getStyle("margin")

	// on changing panel states
	store.studioLayout.leftPanelWidth
	store.studioLayout.rightPanelWidth
	store.studioLayout.showLeftPanel
	store.studioLayout.showRightPanel

	canvasStore.activeCanvas?.activeBreakpoint
	canvasStore.dropTarget.placeholder
	canvasStore.dropTarget.index
	canvasStore.activeCanvas?.canvasProps.breakpoints.map((breakpoint) => breakpoint.visible)

	nextTick(() => {
		tracker.value?.update()
		updateSlotOverlayRefs()
	})
})

// Slot overlay tracking
const showSlotOverlays = computed(() => {
	return (
		props.isPrimaryInstance &&
		isBlockSelected.value &&
		!props.block.isRoot() &&
		Object.keys(props.block.componentSlots).length > 0
	)
})

const slotOverlays = ref<Record<string, HTMLElement>>({})
const slotTrackers = ref<Record<string, Tracker>>({})

const setSlotOverlayRefs = (slotName: string, element: HTMLElement | null) => {
	if (element) {
		slotOverlays.value[slotName] = element
	} else {
		if (slotTrackers.value[slotName]) {
			slotTrackers.value[slotName].cleanup()
		}
		delete slotOverlays.value[slotName]
		delete slotTrackers.value[slotName]
	}
}

const updateSlotOverlayRefs = () => {
	if (!props.target) return

	const slotIDs = new Set(Object.values(props.block.componentSlots).map((slot) => slot.slotId))
	const slotElements = props.target.querySelectorAll("[data-slot-name]")
	const elementsBySlot: Record<string, HTMLElement[]> = {}

	slotElements.forEach((el) => {
		const element = el as HTMLElement
		const slotName = element.dataset.slotName
		const slotId = element.dataset.slotId
		if (!slotName || !slotId || !slotIDs.has(slotId) || !slotOverlays.value[slotName]) return

		if (!elementsBySlot[slotName]) elementsBySlot[slotName] = []
		elementsBySlot[slotName].push(element)
	})

	Object.entries(elementsBySlot).forEach(([slotName, elements]) => {
		// always clean up existing tracker and create a new one since underlying
		// slot elements might completely change, unlike the main component editor
		slotTrackers.value[slotName]?.cleanup()
		slotTrackers.value[slotName] = trackTarget(elements, slotOverlays.value[slotName], canvasProps)
	})

	// Clean up trackers for removed slots
	Object.keys(slotTrackers.value).forEach((slotName) => {
		if (!elementsBySlot[slotName]) {
			slotTrackers.value[slotName].cleanup()
			delete slotTrackers.value[slotName]
		}
	})
}

// watch entire componentSlots object for changes, doesn't work with the common watchEffect
watch(
	() => props.block.componentSlots,
	() => {
		nextTick(updateSlotOverlayRefs)
	},
	{ deep: true, immediate: true },
)

watch(
	() => isBlockSelected.value,
	(newValue, oldValue) => {
		if (newValue === oldValue) return
		nextTick(updateSlotOverlayRefs)
	},
	{ immediate: true },
)

watch(
	() => canvasStore.activeCanvas?.rootComponent,
	() => {
		nextTick(() => {
			tracker.value?.update()
		})
	},
)

onMounted(() => {
	tracker.value = trackTarget(props.target, editor.value, canvasProps)
})

defineExpose({
	element: editor,
})
</script>
