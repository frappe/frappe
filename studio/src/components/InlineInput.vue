<template>
	<div
		class="flex [&>div>input]:!bg-red-600 [&>div>input]:pr-6"
		:class="type === 'textarea' ? 'flex-col gap-1.5' : 'flex-row items-center justify-between'"
	>
		<InputLabel
			:class="[
				enableSlider ? 'cursor-ns-resize' : '',
				required ? `after:text-red-600 after:content-['_*']` : '',
			]"
			@mousedown="handleMouseDown"
		>
			{{ label }}

			<Popover trigger="hover" v-if="description" placement="top">
				<template #target>
					<FeatherIcon name="info" class="ml-1 h-[12px] w-[12px] text-gray-500" />
				</template>
				<template #body>
					<slot name="body">
						<div
							class="w-fit max-w-52 rounded bg-gray-800 px-2 py-1 text-center text-xs text-white shadow-xl"
							v-html="description"
						></div>
					</slot>
				</template>
			</Popover>
		</InputLabel>
		<Autocomplete
			v-if="type === 'autocomplete'"
			placeholder="unset"
			:modelValue="modelValue || ''"
			:options="inputOptions"
			@update:modelValue="handleChange"
			:showInputAsOption="showInputAsOption"
			class="w-full"
			:disabled="disabled"
		/>
		<ColorInput
			v-else-if="type === 'color'"
			:modelValue="modelValue"
			@update:modelValue="handleChange"
			:disabled="disabled"
		/>
		<Input
			v-else
			:type="type"
			:modelValue="modelValue"
			:options="inputOptions"
			@update:modelValue="handleChange"
			@keydown.stop="handleKeyDown"
			:disabled="disabled"
		/>
	</div>
</template>

<script setup lang="ts">
import { isNumber } from "@tiptap/vue-3"
import { Popover } from "frappe-ui"
import { computed } from "vue"
import { extractNumberAndUnit } from "@/utils/helpers"
import Input from "@/components/Input.vue"
import Autocomplete from "@/components/Autocomplete.vue"
import ColorInput from "@/components/ColorInput.vue"
import InputLabel from "@/components/InputLabel.vue"

const props = withDefaults(
	defineProps<{
		modelValue: string | number | boolean | object | null
		label?: string
		description?: string
		type?: string
		unitOptions?: string[]
		options?: Array<string | number | { label: string; value: string }>
		enableSlider?: boolean
		changeFactor?: number
		minValue?: number
		maxValue?: number | null
		showInputAsOption?: boolean
		height?: string
		required?: boolean
		disabled?: boolean
	}>(),
	{
		modelValue: null,
		label: "",
		description: "",
		type: "text",
		unitOptions: () => [],
		options: () => [],
		enableSlider: false,
		changeFactor: 1,
		minValue: 0,
		maxValue: null,
		showInputAsOption: false,
	},
)

const emit = defineEmits(["update:modelValue"])

type Option = {
	label: string
	value: string
}

const inputOptions = computed(() => {
	return (props.options || []).map((option) => {
		if (typeof option === "string" || (typeof option === "number" && props.type === "autocomplete")) {
			return {
				label: option,
				value: option,
			}
		}
		return option
	}) as Option[]
})

// TODO: Refactor
const handleChange = (value: string | number | null | { label: string; value: string }) => {
	if (typeof value === "object" && value !== null && "value" in value) {
		value = value.value
	}
	if (value && typeof value === "string") {
		const { number, unit } = extractNumberAndUnit(value)
		if (!unit && props.unitOptions.length && number) {
			value = number + props.unitOptions[0]
		}
	}

	emit("update:modelValue", value)
}

const handleMouseDown = (e: MouseEvent) => {
	if (!props.enableSlider) return
	const { number } = extractNumberAndUnit(String(props.modelValue || ""))
	const startY = e.clientY
	const startValue = Number(number)
	const handleMouseMove = (e: MouseEvent) => {
		let diff = (startY - e.clientY) * props.changeFactor
		diff = Math.round(diff)
		incrementOrDecrement(diff, startValue)
	}
	const handleMouseUp = () => {
		window.removeEventListener("mousemove", handleMouseMove)
	}
	window.addEventListener("mousemove", handleMouseMove)
	window.addEventListener("mouseup", handleMouseUp, { once: true })
}

const handleKeyDown = (e: KeyboardEvent) => {
	if (!props.enableSlider) return
	if (e.key === "ArrowUp" || e.key === "ArrowDown") {
		const step = e.key === "ArrowUp" ? 1 : -1
		incrementOrDecrement(step)
		e.preventDefault()
	}
}

const incrementOrDecrement = (step: number, initialValue: null | number = null) => {
	const value = String(props.modelValue || "")
	const { number, unit: existingUnit } = extractNumberAndUnit(value)
	const unit =
		existingUnit || (props.unitOptions.length && !isNaN(Number(number)) ? props.unitOptions[0] : "")
	let newValue = (initialValue != null ? Number(initialValue) : Number(number)) + step
	if (isNumber(props.minValue) && newValue <= props.minValue) {
		newValue = props.minValue
	}
	if (isNumber(props.maxValue) && newValue >= props.maxValue) {
		newValue = props.maxValue
	}
	handleChange(newValue + "" + unit)
}
</script>
