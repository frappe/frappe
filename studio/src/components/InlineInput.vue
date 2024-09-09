<template>
	<div
		class="flex [&>div>input]:!bg-red-600 [&>div>input]:pr-6"
		:class="type === 'code'? 'flex-col' : 'flex-row  items-center justify-between'"
	>
		<InputLabel
			:class="{
				'cursor-ns-resize': enableSlider,
			}"
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
			:modelValue="modelValue"
			:options="inputOptions"
			@update:modelValue="handleChange"
			:showInputAsOption="showInputAsOption"
			class="[&>div>select]:dark:border-zinc-700 [&>div>select]:dark:bg-zinc-800 [&>div>select]:dark:text-zinc-200 [&>div>select]:dark:focus:bg-zinc-700 w-full [&>div>select]:text-sm [&>div>select]:text-gray-800"
		/>
		<CodeEditor
			v-else-if="type === 'code'"
			:modelValue="modelValue"
			:type="typeof modelValue == 'function' ? 'JavaScript' : 'JSON'"
			:label="label"
		/>
		<Input
			v-else
			:type="type"
			placeholder="unset"
			:modelValue="modelValue"
			:options="inputOptions"
			@update:modelValue="handleChange"
			@keydown.stop="handleKeyDown"
		/>
	</div>
</template>

<script setup lang="ts">
import { isNumber } from "@tiptap/vue-3"
import { Popover, Autocomplete } from "frappe-ui"
import { PropType, computed } from "vue"
import Input from "@/components/Input.vue"
import CodeEditor from "@/components/CodeEditor.vue"
import InputLabel from "@/components/InputLabel.vue"

const props = defineProps({
	modelValue: {
		type: [String, Number, Boolean, Object, Array],
		default: null,
	},
	label: {
		type: String,
		default: "",
	},
	description: {
		type: String,
		default: "",
	},
	type: {
		type: String,
		default: "text",
	},
	unitOptions: {
		type: Array as PropType<string[]>,
		default: () => [],
	},
	options: {
		type: Array,
		default: () => [],
	},
	enableSlider: {
		type: Boolean,
		default: false,
	},
	changeFactor: {
		type: Number,
		default: 1,
	},
	minValue: {
		type: Number,
		default: 0,
	},
	maxValue: {
		type: Number,
		default: null,
	},
	showInputAsOption: {
		type: Boolean,
		default: false,
	},
})

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
		let [_, number, unit] = value.match(/([0-9]+)([a-z%]*)/) || ["", "", ""]
		if (!unit && props.unitOptions.length && number) {
			value = number + props.unitOptions[0]
		}
	}

	emit("update:modelValue", value)
}

const handleMouseDown = (e: MouseEvent) => {
	if (!props.enableSlider) {
		return
	}
	const number = ((props.modelValue + "" || "") as string).match(/([0-9]+)/)?.[0] || "0"
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
	if (e.key === "ArrowUp" || e.key === "ArrowDown") {
		const step = e.key === "ArrowUp" ? 1 : -1
		incrementOrDecrement(step)
		e.preventDefault()
	}
}

const incrementOrDecrement = (step: number, initialValue: null | number = null) => {
	const value = props.modelValue + "" || ""
	let [_, number, unit] = value.match(/([0-9]+)([a-z%]*)/) || ["", "", ""]
	if (!unit && props.unitOptions.length && !isNaN(Number(number))) {
		unit = props.unitOptions[0]
	}
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
