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
			v-if="!props.block.isRoot()"
			class="absolute -top-3 left-0 inline-block text-xs"
			:class="isBlockSelected ? 'bg-blue-500 text-white' : 'text-blue-500'"
		>
			{{ block.componentName }}
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
				class="pointer-events-none fixed ring-2 ring-inset ring-purple-500"
				:class="isSlotSelected(slot.slotId) ? 'opacity-100' : 'opacity-65'"
				:style="{
					// set min height and width so that slots without content are visible
					minWidth: `calc(${12}px * ${canvasProps.scale})`,
					minHeight: `calc(${12}px * ${canvasProps.scale})`,
				}"
			>
				<span
					class="absolute -top-3 left-0 inline-block text-nowrap text-xs text-white"
					:class="isSlotSelected(slot.slotId) ? 'bg-purple-500' : 'bg-purple-500/65'"
				>
					#{{ slotName }}
				</span>
			</div>
		</template>
	</div>

	<Dialog
		v-if="canvasStore.activeCanvas?.selectedSlot?.slotId"
		v-model="store.showSlotEditorDialog"
		class="overscroll-none"
		:options="{
			title: `Edit #${canvasStore.activeCanvas?.selectedSlot?.slotName} slot for ${block.componentName}`,
			size: '3xl',
		}"
	>
		<template #body-content>
			<Code
				:modelValue="block.getSlotContent(store.selectedSlot?.slotName) || ''"
				language="html"
				height="60vh"
				:showSaveButton="true"
				@save="
					(val) => {
						if (!canvasStore.activeCanvas?.selectedSlot) return
						props.block.updateSlot(canvasStore.activeCanvas?.selectedSlot?.slotName, val)
						store.showSlotEditorDialog = false
					}
				"
			/>
		</template>
	</Dialog>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, Ref, watchEffect, nextTick, inject, watch } from "vue"
import { Dialog } from "frappe-ui"
import BoxResizer from "@/components/BoxResizer.vue"
import PaddingHandler from "@/components/PaddingHandler.vue"
import MarginHandler from "@/components/MarginHandler.vue"
import Code from "@/components/Code.vue"

import Block from "@/utils/block"
import useStudioStore from "@/stores/studioStore"
import useCanvasStore from "@/stores/canvasStore"
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
})

const store = useStudioStore()
const canvasStore = useCanvasStore()
const editor = ref(null) as unknown as Ref<HTMLElement>
const resizing = ref(false)
const tracker = ref<Tracker>()

const canvasProps = inject("canvasProps") as CanvasProps

const showMarginPaddingHandlers = computed(() => {
	return isBlockSelected.value && !props.block.isRoot() && !resizing.value && !canvasStore.isDragging
})

const showResizer = computed(() => {
	return !props.block.isRoot() && isBlockSelected.value && !canvasStore.isDragging
})

const isBlockSelected = computed(() => {
	return props.isSelected && props.breakpoint === canvasStore.activeCanvas?.activeBreakpoint
})

const isSlotSelected = (slotId: string) => {
	return canvasStore.activeCanvas?.selectedSlot?.slotId === slotId
}

const getStyleClasses = computed(() => {
	const classes = ["ring-blue-400"]

	if (isBlockSelected.value && !props.block.isRoot() && !canvasStore.isDragging) {
		// make editor interactive
		classes.push("pointer-events-auto")
		// Place the block on the top of the stack
		classes.push("!z-[19]")
	}
	return classes
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
	return isBlockSelected.value && !props.block.isRoot() && Object.keys(props.block.componentSlots).length > 0
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

	// Find all slot elements within the target
	const slotElements = props.target.querySelectorAll("[data-slot-name]")
	const handledSlots = new Set<string>()

	slotElements.forEach((element) => {
		const slotName = (element as HTMLElement).dataset.slotName
		if (!slotName || !slotOverlays.value[slotName]) return

		handledSlots.add(slotName)

		// always clean up existing tracker and create a new one since underlying
		// slot elements might completely change, unlike the main component editor
		if (slotTrackers.value[slotName]) {
			slotTrackers.value[slotName].cleanup()
		}

		slotTrackers.value[slotName] = trackTarget(
			element as HTMLElement,
			slotOverlays.value[slotName],
			canvasProps,
		)
	})

	// Clean up trackers for removed slots
	Object.keys(slotTrackers.value).forEach((slotName) => {
		if (!handledSlots.has(slotName)) {
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
