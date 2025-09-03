<template>
	<Autocomplete
		size="sm"
		:options="dynamicValueOptions"
		class="!w-auto"
		modelValue=""
		@update:modelValue="(option: VariableOption) => emit('update:modelValue', option.value)"
	>
		<template #target="{ togglePopover }">
			<Tooltip text="Click to set dynamic value" placement="bottom">
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
import Block from "@/utils/block"
import type { VariableOption } from "@/types/Studio/StudioPageVariable"

const props = defineProps<{ block?: Block }>()
const emit = defineEmits<{
	(event: "update:modelValue", value: string): void
}>()
const store = useStudioStore()
const canvasStore = useCanvasStore()

const dynamicValueOptions = computed(() => {
	const groups = []

	if (canvasStore.editingMode === "component") {
		// Component context
		const componentContext = props.block?.componentContext
		if (componentContext && Object.keys(componentContext).length > 0) {
			const inputOptions = Object.keys(componentContext).map((inputName) => ({
				value: `{{ inputs.${inputName} }}`,
				label: `inputs.${inputName}`,
				type: typeof componentContext[inputName],
			}))
			groups.push({
				group: "Component Inputs",
				items: inputOptions,
			})
		}
	} else {
		// Variables group
		if (store.variableOptions.length > 0) {
			groups.push({
				group: "Variables",
				items: store.variableOptions.map((option) => ({
					...option,
					value: `{{ ${option.value} }}`,
				})),
			})
		}
		// Data Sources group
		const dataSourceOptions = Object.keys(store.resources).map((resourceName) => ({
			value: `{{ ${resourceName}.data }}`,
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
	if (repeaterContext && Object.keys(repeaterContext).length > 0) {
		const repeaterOptions = Object.keys(repeaterContext).map((key) => ({
			value: `{{ dataItem.${key} }}`,
			label: `dataItem.${key}`,
			type: typeof repeaterContext[key],
		}))
		groups.push({
			group: "Repeater",
			items: repeaterOptions,
		})
	}

	return groups
})
</script>
