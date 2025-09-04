<template>
	<Autocomplete
		size="sm"
		:options="dynamicValueOptions"
		class="!w-auto"
		modelValue=""
		@update:modelValue="(option: VariableOption) => emit('update:modelValue', option.value)"
	>
		<template #target="{ togglePopover }">
			<slot name="target" v-if="$slots.target" v-bind="{ togglePopover }"></slot>
			<Tooltip v-else text="Click to set dynamic value" placement="bottom">
				<FeatherIcon
					ref="dropdownTrigger"
					name="plus-circle"
					class="mr-1 h-3 w-4 cursor-pointer select-none text-ink-gray-5 outline-none hover:text-ink-gray-9"
					@click="togglePopover"
				/>
			</Tooltip>
		</template>

		<template #item-suffix="{ option }">
			<span class="text-ink-gray-4">{{ option.type?.toLowerCase() }}</span>
		</template>
	</Autocomplete>
</template>

<script setup lang="ts">
import { computed } from "vue"
import { Autocomplete, Tooltip } from "frappe-ui"
import useStudioStore from "@/stores/studioStore"
import useCanvasStore from "@/stores/canvasStore"
import useComponentEditorStore from "@/stores/componentEditorStore"
import Block from "@/utils/block"
import type { VariableOption } from "@/types/Studio/StudioPageVariable"
import type { ComponentInput } from "@/types/Studio/StudioComponent"
import { isObjectEmpty } from "@/utils/helpers"

const props = withDefaults(defineProps<{ block?: Block; formatValuesAsTemplate?: boolean }>(), {
	formatValuesAsTemplate: true,
})
const emit = defineEmits<{
	(event: "update:modelValue", value: string): void
}>()
const store = useStudioStore()
const canvasStore = useCanvasStore()

const formatValue = (value: string) => {
	if (props.formatValuesAsTemplate) {
		return `{{ ${value} }}`
	}
	return value
}

const dynamicValueOptions = computed(() => {
	const groups = []

	if (canvasStore.editingMode === "component") {
		// Component context
		const componentInputs = useComponentEditorStore().componentInputs
		if (!isObjectEmpty(componentInputs)) {
			const componentContext: VariableOption[] = []
			componentInputs.map?.((input: ComponentInput) => {
				componentContext.push({
					value: formatValue(`inputs.${input.input_name}`),
					label: `inputs.${input.input_name}`,
					type: input.type,
				})
			})
			groups.push({
				group: "Component Inputs",
				items: componentContext,
			})
		}
	} else {
		// Variables group
		if (store.variableOptions.length > 0) {
			groups.push({
				group: "Variables",
				items: store.variableOptions.map((option) => ({
					...option,
					value: formatValue(option.value),
				})),
			})
		}
		// Data Sources group
		const dataSourceOptions = Object.keys(store.resources).map((resourceName) => ({
			value: formatValue(`${resourceName}.data`),
			label: resourceName,
			type: "array",
		}))
		if (dataSourceOptions.length > 0) {
			groups.push({
				group: "Data Sources",
				items: dataSourceOptions,
			})
		}
	}

	// Repeater Data Item group
	const repeaterContext = props.block?.repeaterDataItem
	if (!isObjectEmpty(repeaterContext)) {
		const repeaterOptions = Object.keys(repeaterContext!).map((key) => ({
			value: formatValue(`dataItem.${key}`),
			label: `dataItem.${key}`,
			type: typeof repeaterContext![key],
		}))
		groups.push({
			group: "Repeater",
			items: repeaterOptions,
		})
	}

	return groups
})
</script>
