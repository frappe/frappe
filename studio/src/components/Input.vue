<!-- Extracted from Builder -->
<template>
	<div class="relative w-full" :class="type === 'checkbox' ? 'flex items-center' : ''">
		<Select
			v-if="type === 'select'"
			:modelValue="data"
			@update:modelValue="(value: string) => (data = value as typeof data)"
			v-bind="attrs"
			class="w-full"
		/>
		<FormControl
			v-else
			:type="type"
			:modelValue="data"
			@change="triggerUpdate"
			@input="($event: Event) => emit('input', ($event.target as HTMLInputElement).value)"
			autocomplete="off"
			:autofocus="autofocus"
			v-bind="attrs"
		>
			<template #prefix v-if="$slots.prefix">
				<slot name="prefix" />
			</template>
			<template #suffix v-if="$slots.suffix">
				<slot name="suffix" />
			</template>
			<template #suffix v-else-if="!['select', 'checkbox'].includes(type) && !hideClearButton && data">
				<button
					class="cursor-pointer text-ink-gray-4 hover:text-ink-gray-5"
					tabindex="-1"
					@click="clearValue"
				>
					<CrossIcon />
				</button>
			</template>
		</FormControl>
	</div>
</template>
<script lang="ts" setup>
import { FormControl, Select } from "frappe-ui"
import CrossIcon from "@/components/Icons/Cross.vue"
import { useDebounceFn, useVModel } from "@vueuse/core"
import { useAttrs } from "vue"

const props = withDefaults(
	defineProps<{
		modelValue?: string | number | boolean | object | null
		type?: string
		hideClearButton?: boolean
		autofocus?: boolean
	}>(),
	{
		type: "text",
		modelValue: "",
	},
)
const emit = defineEmits(["update:modelValue", "input"])
const data = useVModel(props, "modelValue", emit)

defineOptions({
	inheritAttrs: false,
})

const attrs = useAttrs()

const clearValue = () => {
	data.value = ""
}

const triggerUpdate = useDebounceFn(($event: Event) => {
	if (props.type === "checkbox") {
		emit("update:modelValue", ($event.target as HTMLInputElement).checked)
	} else {
		emit("update:modelValue", ($event.target as HTMLInputElement).value)
	}
}, 100)
</script>
