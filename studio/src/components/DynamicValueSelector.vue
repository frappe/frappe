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
				:tabIndex="-1"
				@click="togglePopover"
			/>
			<IconButton
				v-else
				:icon="LucideCirclePlus"
				label="Click to set dynamic value"
				placement="bottom"
				class="mr-1"
				size="sm"
				:tabIndex="-1"
				@click="togglePopover"
			/>
		</template>

		<template #item-suffix="{ option }">
			<span class="text-ink-gray-4">{{ option.type?.toLowerCase() }}</span>
		</template>
		<template #footer v-if="dynamicValueOptions.length > 0">
			<div class="flex items-center gap-1 px-2" @mousedown.prevent>
				<Tooltip text="Changing the selected variable value will change the prop value and vice versa">
					<FeatherIcon name="info" class="size-3 text-ink-gray-5" />
				</Tooltip>
				<Switch v-model="bindVariable" label="Sync with variable" class="w-full hover:bg-transparent" />
			</div>
		</template>
	</Autocomplete>
</template>

<script setup lang="ts">
import { computed, ref, watch } from "vue"
import { Autocomplete, Switch, Tooltip } from "frappe-ui"
import IconButton from "@/components/IconButton.vue"
import useStudioStore from "@/stores/studioStore"
import useCanvasStore from "@/stores/canvasStore"
import useComponentEditorStore from "@/stores/componentEditorStore"
import Block from "@/utils/block"
import type { VariableOption } from "@/types/Studio/StudioPageVariable"
import type { ComponentInput } from "@/types/Studio/StudioComponent"
import type { SlotScope } from "@/types"
import { isObjectEmpty } from "@/utils/helpers"
import { getBindingType } from "@/utils/parseCode"
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

		// Scoped slot props exposed by the enclosing component (Repeater's dataItem, List's item, ...)
		const slotScopeOptions = getSlotScopeOptions(props.block?.slotScope)
		if (slotScopeOptions.length) {
			groups.push({
				group: "Slot Scope",
				items: slotScopeOptions,
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

		// Page script bindings group (refs/reactive/computed/functions
		const pageScriptOptions = Object.entries(codeStore.pageScriptBindings).map(([name, binding]) => {
			const bindingType = getBindingType(binding)
			const value = bindingType === "function" ? `${name}()` : name
			return {
				value,
				label: name,
				type: bindingType,
			}
		})
		if (pageScriptOptions.length > 0) {
			groups.push({
				group: "Page Script",
				items: pageScriptOptions,
			})
		}
	}

	return groups
})

function getSlotScopeOptions(slotScope?: SlotScope | null): VariableOption[] {
	return Object.entries(slotScope || {}).flatMap(([name, value]) => {
		if (value && typeof value === "object" && !Array.isArray(value)) {
			return Object.keys(value).map((key) => ({
				value: `${name}.${key}`,
				label: `${name}.${key}`,
				type: typeof value[key],
			}))
		}
		return [{ value: name, label: name, type: typeof value }]
	})
}
</script>
