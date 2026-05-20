<template>
	<Combobox
		size="sm"
		:options="dynamicValueOptions"
		class="!w-auto"
		side="left"
		align="start"
		@update:modelValue="(value: string) => emit('update:modelValue', value, bindVariable)"
	>
		<template #trigger="{ togglePopover }">
			<IconButton
				:icon="bindVariable ? Link2 : LucideCirclePlus"
				:label="bindVariable ? 'Synced with variable. Click to change.' : 'Click to set dynamic value'"
				placement="bottom"
				class="mr-1"
				:size="bindVariable ? 'md' : 'sm'"
				:tabIndex="-1"
				@click="togglePopover"
			/>
		</template>

		<template #item-suffix="{ item }">
			<span class="text-ink-gray-4">{{ item.datatype?.toLowerCase() }}</span>
		</template>
		<template #footer v-if="dynamicValueOptions.length > 0">
			<div class="flex items-center gap-1 p-2" @mousedown.prevent>
				<Tooltip text="Changing the selected variable value will change the prop value and vice versa">
					<FeatherIcon name="info" class="size-3 text-ink-gray-5" />
				</Tooltip>
				<Switch v-model="bindVariable" label="Sync with variable" class="w-full hover:bg-transparent" />
			</div>
		</template>
	</Combobox>
</template>

<script setup lang="ts">
import { computed, ref, watch } from "vue"
import { Combobox, Switch, Tooltip } from "frappe-ui"
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
import LucideCirclePlus from "~icons/lucide/circle-plus"

const props = defineProps<{ block?: Block; isVariableBound?: string | null }>()
const emit = defineEmits<{
	(event: "update:modelValue", value: string, bindVariable: boolean): void
}>()
const bindVariable = ref(!!props.isVariableBound)

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
					datatype: input.type as string,
				})
			})
			groups.push({
				group: "Component Inputs",
				options: componentContext,
			})
		}
	} else {
		// Variables group
		if (store.variableOptions.length > 0) {
			groups.push({
				group: "Variables",
				options: store.variableOptions,
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
				datatype: "array",
			}
		})
		if (dataSourceOptions.length > 0) {
			groups.push({
				group: "Data Sources",
				options: dataSourceOptions,
			})
		}
	}

	// Repeater Data Item group
	const repeaterContext = props.block?.repeaterDataItem
	if (!isObjectEmpty(repeaterContext)) {
		const repeaterOptions = Object.keys(repeaterContext!).map((key) => ({
			value: `dataItem.${key}`,
			label: `dataItem.${key}`,
			datatype: typeof repeaterContext![key],
		}))
		groups.push({
			group: "Repeater",
			options: repeaterOptions,
		})
	}

	return groups
})
</script>
