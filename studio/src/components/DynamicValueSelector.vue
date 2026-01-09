<template>
	<Autocomplete
		size="sm"
		:options="dynamicValueOptions"
		class="!w-auto"
		placement="left-start"
		modelValue=""
		@update:modelValue="(option: VariableOption) => emit('update:modelValue', option.value, bindVariable)"
	>
		<template #target="{ togglePopover }">
			<IconButton
				v-if="bindVariable"
				:icon="Link2"
				label="Synced with variable. Click to change."
				placement="bottom"
				class="mr-1"
				@click="togglePopover"
			/>
			<IconButton
				v-else
				icon="plus-circle"
				label="Click to set dynamic value"
				placement="bottom"
				class="mr-1"
				size="sm"
				@click="togglePopover"
			/>
		</template>

		<template #item-suffix="{ option }">
			<span class="text-ink-gray-4">{{ option.type?.toLowerCase() }}</span>
		</template>
		<template #footer>
			<div class="p-1" @mousedown.prevent>
				<Switch
					v-model="bindVariable"
					label="Sync with variable"
					description="Changing the selected variable value will change the prop value and vice versa"
				/>
			</div>
		</template>
	</Autocomplete>
</template>

<script setup lang="ts">
import { computed, ref, watch } from "vue"
import { Autocomplete, Switch } from "frappe-ui"
import IconButton from "@/components/IconButton.vue"
import useStudioStore from "@/stores/studioStore"
import useCanvasStore from "@/stores/canvasStore"
import useComponentEditorStore from "@/stores/componentEditorStore"
import Block from "@/utils/block"
import type { VariableOption } from "@/types/Studio/StudioPageVariable"
import type { ComponentInput } from "@/types/Studio/StudioComponent"
import { isObjectEmpty } from "@/utils/helpers"
import useCodeStore from "@/stores/codeStore"
import Link2 from "~icons/lucide/link-2"

const props = defineProps<{ block?: Block; isVariableBound?: string | null }>()
const emit = defineEmits<{
	(event: "update:modelValue", value: string, bindVariable: boolean): void
}>()
const bindVariable = ref(!!props.isVariableBound)

// Watch for external changes to isVariableBound prop
watch(
	() => props.isVariableBound,
	(newValue) => {
		bindVariable.value = !!newValue
	},
)

const store = useStudioStore()
const canvasStore = useCanvasStore()
const codeStore = useCodeStore()

const dynamicValueOptions = computed(() => {
	const groups = []

	if (canvasStore.editingMode === "component") {
		// Component context
		const componentInputs = useComponentEditorStore().componentInputs
		if (!isObjectEmpty(componentInputs)) {
			const componentContext: VariableOption[] = []
			componentInputs.map?.((input: ComponentInput) => {
				componentContext.push({
					value: `inputs.${input.input_name}`,
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
				items: store.variableOptions,
			})
		}
		// Data Sources group
		const dataSourceOptions = Object.keys(codeStore.resources).map((resourceName) => {
			const completion =
				codeStore.resources[resourceName]?.resource_type === "Document"
					? `${resourceName}.doc`
					: `${resourceName}.data`
			return {
				value: completion,
				label: resourceName,
				type: "array",
			}
		})
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
			value: `dataItem.${key}`,
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
