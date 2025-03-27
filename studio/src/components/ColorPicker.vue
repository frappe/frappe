<!-- Extracted from Builder -->
<template>
	<Popover transition="default" placement="left" class="!block w-full" popoverClass="!min-w-fit !mr-[30px]">
		<template #target="{ togglePopover, isOpen }">
			<slot
				name="target"
				:togglePopover="
					() => {
						togglePopover()
						setSelectorPosition(modelColor)
					}
				"
				:isOpen="isOpen"
			></slot>
		</template>
		<template #body="{ close }">
			<div ref="colorPicker" class="rounded-lg bg-surface-white p-3 shadow-lg">
				<div
					ref="colorMap"
					:style="{
						background: `
							linear-gradient(0deg, black, transparent),
							linear-gradient(90deg, white, transparent),
							hsl(${hue}, 100%, 50%)
						`,
					}"
					@mousedown.prevent="handleSelectorMove"
					class="relative m-auto h-24 w-44 rounded-md"
					@click.prevent="setColor"
				>
					<div
						ref="colorSelector"
						@mousedown.stop.prevent="handleSelectorMove"
						class="absolute rounded-full border border-black border-opacity-20 before:absolute before:h-full before:w-full before:rounded-full before:border-2 before:border-white before:!bg-[currentColor] after:absolute after:left-[2px] after:top-[2px] after:h-[calc(100%-4px)] after:w-[calc(100%-4px)] after:rounded-full after:border after:border-black after:border-opacity-20 after:bg-transparent"
						:style="
							{
								height: '12px',
								width: '12px',
								left: `calc(${colorSelectorPosition.x}px - 6px)`,
								top: `calc(${colorSelectorPosition.y}px - 6px)`,
								color: modelColor || '#FFF',
								background: 'transparent',
							} as StyleValue
						"
					></div>
				</div>
				<div
					ref="hueMap"
					class="relative m-auto mt-2 h-3 w-44 rounded-md"
					@click="setHue"
					@mousedown.prevent="handleHueSelectorMove"
					:style="{
						background: `
							linear-gradient(90deg, hsl(0, 100%, 50%),
							hsl(60, 100%, 50%), hsl(120, 100%, 50%),
							hsl(180, 100%, 50%), hsl(240, 100%, 50%),
							hsl(300, 100%, 50%), hsl(360, 100%, 50%))
						`,
					}"
				>
					<div
						ref="hueSelector"
						@mousedown="handleHueSelectorMove"
						class="absolute rounded-full border border-[rgba(0,0,0,.2)] before:absolute before:h-full before:w-full before:rounded-full before:border-2 before:border-white before:bg-[currentColor] after:absolute after:left-[2px] after:top-[2px] after:h-[calc(100%-4px)] after:w-[calc(100%-4px)] after:rounded-full after:border after:border-[rgba(0,0,0,.2)] after:bg-transparent"
						:style="{
							height: '12px',
							width: '12px',
							left: `calc(${hueSelectorPosition.x}px - 6px)`,
							color: `hsl(${hue}, 100%, 50%)`,
							background: 'transparent',
						}"
					></div>
				</div>
				<div ref="colorPalette" class="max-w-[11rem]">
					<div class="mt-3 flex flex-wrap gap-1.5">
						<div
							v-for="color in colors"
							:key="color"
							class="h-3.5 w-3.5 cursor-pointer rounded-full shadow-sm"
							@click="
								() => {
									setSelectorPosition(color)
									updateColor()
								}
							"
							:style="{
								background: color,
							}"
						></div>
						<EyeDropperIcon v-if="isSupported" class="text-ink-gray-7" @click="() => open()" />
					</div>
				</div>
			</div>
		</template>
	</Popover>
</template>
<script setup lang="ts">
import { PropType, Ref, StyleValue, computed, nextTick, ref, watch } from "vue"
import EyeDropperIcon from "@/components/Icons/EyeDropper.vue"
import useCanvasStore from "@/stores/canvasStore"
import { HSVToHex, HexToHSV, getRGB } from "@/utils/helpers"
import { clamp, useEyeDropper } from "@vueuse/core"
import { Popover } from "frappe-ui"
import type { HashString, RGBString } from "@/types"

const canvasStore = useCanvasStore()

const hueMap = ref(null) as unknown as Ref<HTMLDivElement>
const colorMap = ref(null) as unknown as Ref<HTMLDivElement>
const hueSelector = ref(null) as unknown as Ref<HTMLDivElement>
const colorSelector = ref(null) as unknown as Ref<HTMLDivElement>

const colorSelectorPosition = ref({ x: 0, y: 0 })
const hueSelectorPosition = ref({ x: 0, y: 0 })
let currentColor = "#FFF" as HashString

const { isSupported, sRGBHex, open } = useEyeDropper()

const props = defineProps({
	modelValue: {
		type: String as PropType<HashString | RGBString | null>,
		default: null,
	},
})

const modelColor = computed(() => {
	return getRGB(props.modelValue)
})

const emit = defineEmits(["update:modelValue"])

const colors = [
	"#FFB3E6",
	"#00B3E6",
	"#E6B333",
	"#3366E6",
	"#999966",
	"#99FF99",
	"#B34D4D",
	"#80B300",
] as HashString[]

if (!isSupported.value) {
	colors.push("#B34D4D")
}
// frappe-ui grays
colors.push("#F3F3F3", "#EDEDED")

const setColorSelectorPosition = (color: HashString) => {
	const { width, height } = colorMap.value.getBoundingClientRect()
	const { s, v } = HexToHSV(color)
	let x = clamp(s * width, 0, width)
	let y = clamp((1 - v) * height, 0, height)
	colorSelectorPosition.value = { x, y }
}

const setHueSelectorPosition = (color: HashString) => {
	const { width } = hueMap.value.getBoundingClientRect()
	const { h } = HexToHSV(color)
	const left = (h / 360) * width
	hueSelectorPosition.value = { x: left, y: 0 }
}

const handleSelectorMove = (ev: MouseEvent) => {
	setColor(ev)
	const pauseId = canvasStore.activeCanvas?.history?.pause()
	const mouseMove = (mouseMoveEvent: MouseEvent) => {
		mouseMoveEvent.preventDefault()
		setColor(mouseMoveEvent)
	}
	document.addEventListener("mousemove", mouseMove)
	document.addEventListener(
		"mouseup",
		(mouseUpEvent) => {
			document.removeEventListener("mousemove", mouseMove)
			mouseUpEvent.preventDefault()
			pauseId && canvasStore.activeCanvas?.history?.resume(pauseId, true)
		},
		{ once: true },
	)
}

const handleHueSelectorMove = (ev: MouseEvent) => {
	setHue(ev)
	const pauseId = canvasStore.activeCanvas?.history?.pause()
	const mouseMove = (mouseMoveEvent: MouseEvent) => {
		mouseMoveEvent.preventDefault()
		setHue(mouseMoveEvent)
	}
	document.addEventListener("mousemove", mouseMove)
	document.addEventListener(
		"mouseup",
		(mouseUpEvent) => {
			document.removeEventListener("mousemove", mouseMove)
			mouseUpEvent.preventDefault()
			pauseId && canvasStore.activeCanvas?.history?.resume(pauseId, true)
		},
		{ once: true },
	)
}

function setColor(ev: MouseEvent) {
	const clickPointX = ev.clientX
	const clickPointY = ev.clientY
	const colorMapBounds = colorMap.value.getBoundingClientRect()

	let pointX = clickPointX - colorMapBounds.left
	let pointY = clickPointY - colorMapBounds.top

	pointX = clamp(pointX, 0, colorMapBounds.width)
	pointY = clamp(pointY, 0, colorMapBounds.height)
	colorSelectorPosition.value = { x: pointX, y: pointY }
	updateColor()
}

function setHue(ev: MouseEvent) {
	const hueMapBounds = hueMap.value.getBoundingClientRect()
	const { clientX } = ev
	let point = clientX - hueMapBounds.left
	point = clamp(point, 0, hueMapBounds.width)
	hueSelectorPosition.value = { x: point, y: 0 }
	updateColor()
}

function setSelectorPosition(color: HashString | null) {
	if (!color) {
		colorSelectorPosition.value = { x: 0, y: 0 }
		hueSelectorPosition.value = { x: 0, y: 0 }
		return
	}
	nextTick(() => {
		setColorSelectorPosition(color)
		setHueSelectorPosition(color)
	})
}

const hue = computed(() => {
	if (!hueMap.value) return 0
	const positionX = hueSelectorPosition.value.x || 0
	const width = hueMap.value.getBoundingClientRect().width || 1
	return Math.round((positionX / width) * 360)
})

const updateColor = () => {
	nextTick(() => {
		const colorMapBounds = colorMap.value.getBoundingClientRect()
		const s = Math.round((colorSelectorPosition.value.x / colorMapBounds.width) * 100)
		const v = 100 - Math.round((colorSelectorPosition.value.y / colorMapBounds.height) * 100)
		const h = hue.value
		currentColor = HSVToHex(h, s, v)
		emit("update:modelValue", currentColor)
	})
}

watch(sRGBHex, () => {
	if (!isSupported.value || !sRGBHex.value) return
	emit("update:modelValue", sRGBHex.value)
})

watch(
	() => props.modelValue,
	(color) => {
		if (color === currentColor) return
		setSelectorPosition(getRGB(color))
	},
	{ immediate: true },
)
</script>
