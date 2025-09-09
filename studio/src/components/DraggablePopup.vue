<!-- Extracted from Builder -->
<template>
	<teleport to="body">
		<div class="relative" ref="popover">
			<div class="fixed z-50" @mousedown.stop>
				<div
					ref="popoverContent"
					class="fixed flex flex-col gap-1 overflow-hidden rounded-lg border border-outline-gray-2 bg-surface-white shadow-2xl"
					:style="{
						width: width + 'px',
						minHeight: height + 'px',
						left: popupLeft + 'px',
						top: popupTop + 'px',
					}"
				>
					<div
						class="flex cursor-grab select-none items-center justify-between px-4 py-2 pr-3 text-sm text-ink-gray-9"
						:class="{ 'cursor-grabbing': isDragging }"
						@mousedown="startDrag"
					>
						<slot name="header"></slot>
						<div class="flex items-center gap-2">
							<Button
								v-if="actionLabel && actionHandler"
								@click="actionHandler"
								:label="actionLabel"
								variant="solid"
							></Button>
							<Button @click="togglePopup" icon="x" variant="subtle"></Button>
						</div>
					</div>
					<div class="flex-1 px-3 pb-3">
						<slot name="content"></slot>
					</div>
				</div>
			</div>
		</div>
	</teleport>
</template>

<script setup lang="ts">
import { useEventListener } from "@vueuse/core"
import { nextTick, onMounted, Ref, ref } from "vue"

const popover = ref(null) as Ref<HTMLElement | null>

const props = withDefaults(
	defineProps<{
		modelValue: boolean
		width?: number
		height?: number
		placement?:
			| "top-left"
			| "top-right"
			| "bottom-left"
			| "bottom-right"
			| "center"
			| "top-middle"
			| "bottom-middle"
			| "middle-left"
			| "middle-right"
		placementOffset?: number
		clickOutsideToClose?: boolean
		container?: HTMLElement | null
		actionLabel?: string
		actionHandler?: () => void
	}>(),
	{
		width: 300,
		height: 200,
		clickOutsideToClose: false,
		placement: "top-left",
		placementOffset: 0,
	},
)

const emit = defineEmits(["update:modelValue"])

const popoverContent = ref(null) as Ref<HTMLElement | null>
const popupLeft = ref(1500)
const popupTop = ref(100)
let isDragging = ref(false)

let startX = 0
let startY = 0
let startLeft = 0
let startTop = 0

onMounted(async () => {
	await nextTick()
	setPosition()
})

const togglePopup = () => {
	emit("update:modelValue", !props.modelValue)
}

const startDrag = (event: MouseEvent) => {
	isDragging.value = true
	startX = event.clientX
	startY = event.clientY
	startLeft = popupLeft.value
	startTop = popupTop.value

	document.addEventListener("mousemove", drag)
	document.addEventListener("mouseup", stopDrag, { once: true })
}

const drag = (event: MouseEvent) => {
	if (!isDragging.value) return
	const dx = event.clientX - startX
	const dy = event.clientY - startY
	popupLeft.value = startLeft + dx
	popupTop.value = startTop + dy
}

const stopDrag = () => {
	isDragging.value = false
	document.removeEventListener("mousemove", drag)
}

const handleClickOutside = (event: Event) => {
	if (props.modelValue && popoverContent.value && !popoverContent.value.contains(event.target as Node)) {
		emit("update:modelValue", false)
	}
}

const setPosition = () => {
	if (props.container) {
		const { left, top, right, bottom } = props.container.getBoundingClientRect()
		switch (props.placement) {
			case "top-left":
				popupLeft.value = left + props.placementOffset
				popupTop.value = top + props.placementOffset
				break
			case "top-right":
				popupLeft.value = right - props.width - props.placementOffset
				popupTop.value = top + props.placementOffset
				break
			case "bottom-left":
				popupLeft.value = left + props.placementOffset
				popupTop.value = bottom - props.height - props.placementOffset
				break
			case "bottom-right":
				popupLeft.value = right - props.width - props.placementOffset
				popupTop.value = bottom - props.height - props.placementOffset
				break
			case "center":
				popupLeft.value = left + (right - left) / 2 - props.width / 2
				popupTop.value = top + (bottom - top) / 2 - props.height / 2
				break
			case "top-middle":
				popupLeft.value = left + (right - left) / 2 - props.width / 2
				popupTop.value = top + props.placementOffset
				break
			case "bottom-middle":
				popupLeft.value = left + (right - left) / 2 - props.width / 2
				popupTop.value = bottom - props.height - props.placementOffset
				break
			case "middle-left":
				popupLeft.value = left + props.placementOffset
				popupTop.value = top + (bottom - top) / 2 - props.height / 2
				break
			case "middle-right":
				popupLeft.value = right - props.width - props.placementOffset
				popupTop.value = top + (bottom - top) / 2 - props.height / 2
				break
		}
	} else {
		const { innerWidth, innerHeight } = window
		popupLeft.value = innerWidth / 2 - props.width / 2
		popupTop.value = innerHeight / 2 - props.height / 2
	}
}

if (props.clickOutsideToClose) {
	useEventListener(document, "click", handleClickOutside, {
		capture: true,
		passive: true,
	})
}

useEventListener(window, "resize", setPosition)
</script>
