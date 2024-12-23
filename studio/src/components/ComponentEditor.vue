<template>
	<ComponentContextMenu :block="block" :editable="false" v-slot="{ onContextMenu }">
		<div
			class="editor pointer-events-none fixed z-[18] box-content select-none ring-2 ring-inset"
			ref="editor"
			:selected="isBlockSelected"
			:data-component-id="block.componentId"
			:class="getStyleClasses"
			@contextmenu="onContextMenu"
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
				:on-update="updateTracker"
				:disable-handlers="false"
				:breakpoint="breakpoint"
			/>
			<MarginHandler
				v-if="showMarginPaddingHandlers"
				:target-block="block"
				:target="target"
				:on-update="updateTracker"
				:disable-handlers="false"
				:breakpoint="breakpoint"
			/>
			<BoxResizer v-if="showResizer" :targetBlock="block" @resizing="resizing = $event" :target="target" />

			<!-- Slot Overlays -->
			<template v-if="showSlotOverlays" v-for="(slot, slotName) in block.componentSlots" :key="slotName">
				<div
					:ref="(el) => setSlotOverlayRef(slotName, el)"
					:data-slot-name="slotName"
					:data-slot-id="slot.slotId"
					class="pointer-events-none fixed ring-2 ring-inset ring-purple-500"
					:class="isSlotSelected(slot.slotId) ? 'opacity-100' : 'opacity-65'"
					:style="{
						// set min height and width so that slots without content are visible
						minWidth: `calc(${12}px * ${canvasProps.scale})`,
						minHeight: `calc(${12}px * ${canvasProps.scale})`,
					}"
				>
					<span
						class="absolute -top-3 left-0 inline-block text-xs text-white"
						:class="isSlotSelected(slot.slotId) ? 'bg-purple-500' : 'bg-purple-500/65'"
					>
						#{{ slotName }}
					</span>
				</div>
			</template>
		</div>
	</ComponentContextMenu>

	<Dialog
		v-if="store.selectedSlot?.slotId"
		v-model="store.showSlotEditorDialog"
		class="overscroll-none"
		:options="{
			title: `Edit #${store.selectedSlot?.slotName} slot for ${block.componentName}`,
			size: '3xl',
		}"
	>
		<template #body-content>
			<CodeEditor
				:modelValue="block.getSlotContent(store.selectedSlot?.slotName) || ''"
				type="HTML"
				height="60vh"
				:showLineNumbers="true"
				:showSaveButton="true"
				@save="
					(val) => {
						if (!store.selectedSlot) return
						props.block.updateSlot(store.selectedSlot?.slotName, val)
						store.showSlotEditorDialog = false
					}
				"
				required
			/>
		</template>
	</Dialog>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted, Ref, watchEffect, nextTick, inject, watch } from "vue"

import ComponentContextMenu from "@/components/ComponentContextMenu.vue"
import BoxResizer from "@/components/BoxResizer.vue"
import PaddingHandler from "@/components/PaddingHandler.vue"
import MarginHandler from "@/components/MarginHandler.vue"
import CodeEditor from "@/components/CodeEditor.vue"

import Block from "@/utils/block"
import useStudioStore from "@/stores/studioStore"
import trackTarget from "@/utils/trackTarget"

import { CanvasProps } from "@/types"

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
const editor = ref(null) as unknown as Ref<HTMLElement>
const resizing = ref(false)
const updateTracker = ref(() => {})

const canvasProps = inject("canvasProps") as CanvasProps

const showMarginPaddingHandlers = computed(() => {
	return false
	return isBlockSelected.value && !props.block.isRoot() && !resizing.value
})

const showResizer = computed(() => {
	return !props.block.isRoot() && isBlockSelected.value
})

const isBlockSelected = computed(() => {
	return props.isSelected && props.breakpoint === store.activeBreakpoint
})

const isSlotSelected = (slotId: string) => {
	return store.selectedSlot?.slotId === slotId
}

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

const preventCLick = ref(false)
const handleClick = (ev: MouseEvent) => {
	if (preventCLick.value) {
		preventCLick.value = false
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
	const parentBlock = props.block.getParentBlock()
	// on rearranging blocks
	parentBlock?.getChildIndex(props.block)

	// on changing panel states
	store.studioLayout.leftPanelWidth
	store.studioLayout.rightPanelWidth
	store.studioLayout.showLeftPanel
	store.studioLayout.showRightPanel

	store.activeBreakpoint
	store.canvas?.canvasProps.breakpoints.map((breakpoint) => breakpoint.visible)

	nextTick(() => {
		updateTracker.value()
	})
})

// Slot Overlays
const showSlotOverlays = computed(() => {
	return isBlockSelected.value && !props.block.isRoot() && Object.keys(props.block.componentSlots).length > 0
})

const slotOverlays = reactive<
	Record<
		string,
		{
			element: HTMLElement | null
			tracker: (() => void) | null
		}
	>
>({})
const setSlotOverlayRef = (slotName: string, element: HTMLElement | null) => {
	if (element) {
		// If the slot doesn't exist, create it
		if (!slotOverlays[slotName]) {
			slotOverlays[slotName] = {
				element: null,
				tracker: null,
			}
		}
		// Update the element
		slotOverlays[slotName].element = element
		slotOverlays[slotName].tracker?.()
	} else {
		delete slotOverlays[slotName]
	}
}

const updateSlotOverlayRefs = () => {
	if (!props.target) return

	// Find all slot elements within the target
	const slotElements = props.target.querySelectorAll("[data-slot-name]")

	slotElements.forEach((element) => {
		const slotName = (element as HTMLElement).dataset.slotName

		if (slotName && slotOverlays[slotName]?.element) {
			slotOverlays[slotName].tracker = trackTarget(
				element as HTMLElement,
				slotOverlays[slotName].element!,
				store.canvas?.canvasProps as CanvasProps,
			)
		}
	})
}

// watch entire componentSlots object for changes, doesn't work with watchEffect
watch(
	() => props.block.componentSlots,
	() => {
		nextTick(updateSlotOverlayRefs)
	},
	{ deep: true },
)

watchEffect(() => {
	if (isBlockSelected.value) {
		nextTick(updateSlotOverlayRefs)
	}
})

onMounted(() => {
	updateTracker.value = trackTarget(props.target, editor.value, store.canvas?.canvasProps as CanvasProps)
	updateSlotOverlayRefs()
})

defineExpose({
	element: editor,
})
</script>
