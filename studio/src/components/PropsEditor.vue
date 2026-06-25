<template>
	<EmptyState
		v-if="isObjectEmpty(componentProps)"
		:message="`${block?.getBlockDescription()} has no editable properties`"
	/>
	<div v-else class="mt-3 flex flex-col gap-3">
		<div
			v-for="(config, propName) in filteredComponentProps"
			:key="propName"
			class="group flex w-full items-center"
		>
			<DynamicValueSelector
				v-if="!isTestingComponent"
				:block="block"
				@update:modelValue="(value, bindVariable) => setDynamicValue(propName, value, bindVariable)"
				:class="{ 'mt-1 self-start': isCodeField(config.inputType) }"
				:isVariableBound="isVariableBound(config.modelValue)"
			/>

			<Code
				v-if="config.inputType === 'html'"
				:label="propName"
				language="html"
				:modelValue="getFormattedValue(propName)"
				@update:modelValue="(newValue) => handlePropUpdate(propName, newValue)"
				:required="config.required"
				:completions="(context: CompletionContext) => getCompletions(context, block?.getCompletions())"
				:showLineNumbers="false"
				height="250px"
				class="overflow-hidden"
				:actionButton="{
					icon: 'lucide-maximize',
					label: 'Expand',
					handler: () => {
						if (!props.block) return
						canvasStore.editHTML(props.block)
					},
				}"
			/>
			<template v-else-if="config.inputType === 'code' || config.inputType === 'array'">
				<div class="relative min-w-0 flex-1">
					<Button
						v-if="config.inputType === 'array'"
						:tabIndex="-1"
						variant="ghost"
						size="sm"
						@click="toggleArrayInputs(propName)"
						:icon="arrayInputs[propName] === 'code' ? 'lucide-table' : 'lucide-code'"
						class="absolute right-0 top-0 z-10 hover:bg-transparent"
						:tooltip="arrayInputs[propName] === 'code' ? 'Switch to table editor' : 'Switch to code editor'"
					></Button>
					<Code
						v-if="config.inputType === 'code' || arrayInputs[propName] === 'code'"
						:label="propName"
						language="javascript"
						:modelValue="getFormattedValue(propName)"
						@update:modelValue="(newValue) => handlePropUpdate(propName, newValue)"
						:required="config.required"
						:completions="(context: CompletionContext) => getCompletions(context, block?.getCompletions())"
						:showLineNumbers="false"
						class="overflow-hidden"
						:actionButton="{
							icon: 'lucide-maximize',
							label: 'Expand',
							handler: () => {
								if (!props.block) return
								canvasStore.editCode(props.block, propName, getFormattedValue(propName))
							},
						}"
					/>
					<ArrayInput
						v-else-if="config.inputType === 'array'"
						:label="propName"
						:required="config.required"
						:modelValue="getFormattedValue(propName)"
						@update:modelValue="(newValue) => handlePropUpdate(propName, newValue)"
						:itemTypes="config.itemTypes"
					/>
				</div>
			</template>
			<InlineInput
				v-else
				:label="propName"
				:type="config.inputType"
				:options="config.options"
				:required="config.required"
				:modelValue="getFormattedValue(propName)"
				@update:modelValue="(newValue) => handlePropUpdate(propName, newValue)"
				class="flex-1"
				v-bind="config.props"
			/>
		</div>
	</div>
</template>

<script setup lang="ts">
import { computed, ref } from "vue"
import EmptyState from "@/components/EmptyState.vue"
import Block from "@/utils/block"

import InlineInput from "@/components/InlineInput.vue"
import ArrayInput from "@/components/ArrayInput.vue"
import { isObjectEmpty } from "@/utils/helpers"
import Code from "@/components/Code.vue"
import { useStudioCompletions } from "@/utils/useStudioCompletions"
import type { CompletionContext } from "@codemirror/autocomplete"
import useComponentStore from "@/stores/componentStore"
import { getComponentProps } from "@/utils/components"
import { isDynamicValue } from "@/utils/code"
import useCanvasStore from "@/stores/canvasStore"
import useComponentEditorStore from "@/stores/componentEditorStore"
import type { ComponentProps } from "@/types"
import { ComponentInput } from "@/types/Studio/StudioComponent"
import DynamicValueSelector from "@/components/DynamicValueSelector.vue"
import useStudioStore from "@/stores/studioStore"
import useComponentInstance from "@/utils/useComponentInstance"

const props = defineProps<{
	block?: Block
	isTestingComponent?: boolean
}>()

const getCompletions = useStudioCompletions()
const canvasStore = useCanvasStore()
const store = useStudioStore()

const componentInstance = useComponentInstance(() => props.block)

const componentProps = computed(() => {
	if (!props.block || props.block.isRoot()) return {}

	let propConfig
	if (props.isTestingComponent) {
		const componentEditorStore = useComponentEditorStore()
		propConfig = getStudioComponentProps(componentEditorStore.componentInputs)
	} else if (props.block.isStudioComponent) {
		const componentStore = useComponentStore()
		const componentDoc = componentStore.getComponentDoc(props.block.componentName)
		if (componentDoc?.inputs) {
			propConfig = getStudioComponentProps(componentDoc?.inputs)
		}
	} else if (componentInstance.value) {
		propConfig = getComponentProps(props.block.componentName, componentInstance.value)
	}
	if (!propConfig) return {}

	const currentProps = props.block?.componentProps
	const filteredProps: typeof propConfig = {}

	Object.entries(propConfig).forEach(([propName, config]) => {
		const showProp = config.condition ? config.condition(currentProps) : true
		if (!showProp) {
			props.block?.removeProp(propName)
			return
		}

		if (props.block?.componentProps[propName] === undefined) {
			const defaultValue = typeof config.default === "function" ? config.default() : config.default
			config.modelValue = defaultValue
			if (defaultValue !== undefined) {
				props.block?.setProp(propName, defaultValue)
			}
		} else {
			config.modelValue = props.block.componentProps[propName]
		}

		if (
			(isDynamicValue(config.modelValue) || isVariableBound(config.modelValue)) &&
			!isCodeField(config.inputType)
		) {
			config.inputType = "code"
		}
		filteredProps[propName] = config
	})

	return filteredProps
})

const filteredComponentProps = computed(() => {
	if (!store.propertyFilter) {
		return componentProps.value
	}

	const filter = store.propertyFilter.toLowerCase()
	const filtered: typeof componentProps.value = {}

	Object.entries(componentProps.value).forEach(([propName, config]) => {
		if (propName.toLowerCase().includes(filter)) {
			filtered[propName] = config
		}
	})

	return filtered
})

const hasFilteredProps = computed(() => !isObjectEmpty(filteredComponentProps.value))
defineExpose({ hasFilteredProps })

function getStudioComponentProps(componentInputs: ComponentInput[]): ComponentProps {
	if (isObjectEmpty(componentInputs)) return {}

	const _props: ComponentProps = {}
	componentInputs.forEach((input) => {
		_props[input.input_name] = {
			type: input.type,
			default: input.default || undefined,
			inputType: input.type,
			required: !!input.required,
			options:
				input.type === "select"
					? input.options?.split("\n").map((opt: string) => ({ value: opt, label: opt }))
					: undefined,
			props: input.type === "color" ? { showTokens: false } : {},
		}
	})
	return _props
}

const isCodeField = (inputType: string) => {
	return ["code", "html", "array"].includes(inputType)
}

function setDynamicValue(propName: string, varName: string, bindVariable: boolean) {
	if (bindVariable) {
		props.block?.setProp(propName, { $type: "variable", name: varName })
	} else {
		props.block?.setProp(propName, `{{ ${varName} }}`)
	}
}

const getFormattedValue = (propName: string) => {
	const value = props.block?.componentProps[propName]
	if (value?.$type === "variable") {
		return `{{ ${value.name} }}`
	}
	return value
}

const handlePropUpdate = (propName: string, newValue: any) => {
	props.block?.setProp(propName, newValue)
}

const isVariableBound = (value: any) => {
	return value?.$type === "variable" ? value.name : null
}

const arrayInputs = ref<Record<string, "code" | "table">>({})
const toggleArrayInputs = (propName: string) => {
	if (arrayInputs.value[propName] === "code") {
		arrayInputs.value[propName] = "table"
	} else {
		arrayInputs.value[propName] = "code"
	}
}
</script>
