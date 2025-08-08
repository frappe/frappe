<!-- Extracted from Builder -->
<template>
	<div class="relative w-full">
		<FormControl
			:class="classes"
			:type="type"
			@change="triggerUpdate"
			@input="($event: Event) => emit('input', ($event.target as HTMLInputElement).value)"
			autocomplete="off"
			:autofocus="autofocus"
			v-bind="attrs"
			:modelValue="data"
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
import CrossIcon from "@/components/Icons/Cross.vue"
import { useDebounceFn, useVModel } from "@vueuse/core"
import { computed, useAttrs } from "vue"

const props = withDefaults(
	defineProps<{
		modelValue?: string | number | boolean | null
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

const classes = computed(() => {
	const _classes = []
	if (!["select", "checkbox"].includes(props.type) && !props.hideClearButton && props.modelValue) {
		_classes.push("[&>div>input]:pr-7")
	}
	if (props.type === "checkbox") {
		_classes.push("[&>label]:text-ink-gray-7")
	}

	if (attrs.variant === "outline") {
		return _classes
	}

	if (props.type === "select") {
		_classes.push(
			...[
				"[&>div>select]:text-ink-gray-8",
				"[&>label]:text-ink-gray-7",
				"[&>div>select]:border-outline-gray-1",
				"[&>div>select]:bg-surface-gray-2",
				"[&>div>select]:pr-7",
				"[&>div>select]:hover:border-outline-gray-2",
				"[&>div>select]:hover:bg-surface-gray-1",
				"focus:[&>div>select]:bg-surface-gray-1",
				"focus:[&>div>select]:border-outline-gray-3",
				"focus:[&>div>select]:ring-outline-gray-3",
			],
		)
	} else if (props.type === "textarea") {
		_classes.push([
			"[&>div>textarea]:border-outline-gray-1",
			"[&>label]:text-ink-gray-7",
			"[&>div>textarea]:!bg-surface-gray-2",
			"[&>div>textarea]:text-ink-gray-8",
			"[&>div>textarea]:focus:border-outline-gray-3",
			"[&>div>textarea]:focus:bg-surface-gray-1",
			"[&>div>textarea]:hover:!border-outline-gray-2",
			"[&>div>textarea]:hover:!bg-surface-gray-1",
			"focus:[&>div>textarea]:border-outline-gray-3",
			"focus:[&>div>textarea]:bg-surface-gray-1",
			"focus:[&>div>textarea]:ring-outline-gray-3",
		])
	} else {
		_classes.push([
			"[&>label]:text-ink-gray-7",
			"[&>div>input]:border-outline-gray-1",
			"[&>div>input]:bg-surface-gray-2",
			"[&>div>input]:text-ink-gray-8",
			"text-sm",
			"[&>p]:text-p-xs",
			"[&>div>input]:hover:!border-outline-gray-2",
			"[&>div>input]:hover:!bg-surface-gray-1",
			"[&>div>input]:focus-visible:bg-surface-gray-1",
			"focus:[&>div>input]:border-outline-gray-3",
			"focus:[&>div>input]:bg-surface-gray-1",
			"focus:[&>div>input]:ring-outline-gray-3",
		])
	}
	return _classes
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
