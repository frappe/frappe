<template>
	<Dropdown :options="dropdownOptions">
		<FeatherIcon
			ref="dropdownTrigger"
			name="plus-circle"
			class="mr-1 h-3 w-4 cursor-pointer select-none text-ink-gray-5 outline-none hover:text-ink-gray-9"
		/>
	</Dropdown>
</template>

<script setup lang="ts">
import { computed, ref } from "vue"
import { Dropdown } from "frappe-ui"
import useStudioStore from "@/stores/studioStore"
import useCanvasStore from "@/stores/canvasStore"
import useComponentEditorStore from "@/stores/componentEditorStore"
import Block from "@/utils/block"
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

const isDynamicValueEnabled = ref(false)
const formatValue = (value: string) => {
	if (props.formatValuesAsTemplate) {
		return `{{ ${value} }}`
	}
	return value
}

const dropdownOptions = computed(() => {
	const options = []

	// Toggle switch for "Set Dynamic Value"
	options.push({
		label: "Set Dynamic Value",
		switch: true,
		switchValue: isDynamicValueEnabled.value,
		onClick: () => {
			console.log("Toggling dynamic value")
			isDynamicValueEnabled.value = !isDynamicValueEnabled.value
			emit("update:modelValue", isDynamicValueEnabled.value ? "{{ }}" : "")
		},
	})

	// Dynamic value options
	if (canvasStore.editingMode === "component") {
		// Component context
		const componentInputs = useComponentEditorStore().componentInputs
		if (!isObjectEmpty(componentInputs)) {
			const componentItems = componentInputs.map?.((input: ComponentInput) => ({
				label: `inputs.${input.input_name}`,
				onClick: () => emit("update:modelValue", formatValue(`inputs.${input.input_name}`)),
			}))
			options.push({
				group: "Component Inputs",
				items: componentItems,
			})
		}
	} else {
		// Variables group
		if (store.variableOptions.length > 0) {
			const variableItems = store.variableOptions.map((option) => ({
				label: option.label,
				onClick: () => emit("update:modelValue", formatValue(option.value)),
			}))
			options.push({
				group: "Variables",
				items: variableItems,
			})
		}

		// Data Sources group
		const dataSourceOptions = Object.keys(store.resources).map((resourceName) => {
			const completion =
				store.resources[resourceName]?.resource_type === "Document"
					? `${resourceName}.doc`
					: `${resourceName}.data`
			return {
				label: resourceName,
				onClick: () => emit("update:modelValue", formatValue(completion)),
			}
		})
		if (dataSourceOptions.length > 0) {
			options.push({
				group: "Data Sources",
				items: dataSourceOptions,
			})
		}
	}

	// Repeater Data Item group
	const repeaterContext = props.block?.repeaterDataItem
	if (!isObjectEmpty(repeaterContext)) {
		const repeaterItems = Object.keys(repeaterContext!).map((key) => ({
			label: `dataItem.${key}`,
			onClick: () => emit("update:modelValue", formatValue(`dataItem.${key}`)),
		}))
		options.push({
			group: "Repeater",
			items: repeaterItems,
		})
	}

	return options
})
</script>
