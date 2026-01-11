<template>
	<EmptyState
		v-if="isObjectEmpty(componentProps)"
		:message="`${block?.getBlockDescription()} has no editable properties`"
	/>
	<div v-else class="mt-3 flex flex-col gap-3">
		<div v-for="(config, propName) in componentProps" :key="propName" class="group flex w-full items-center">
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
					icon: 'maximize-2',
					label: 'Expand',
					handler: () => {
						if (!props.block) return
						canvasStore.editHTML(props.block)
					},
				}"
			/>
			<Code
				v-else-if="config.inputType === 'code'"
				:label="propName"
				language="javascript"
				:modelValue="getFormattedValue(propName)"
				@update:modelValue="(newValue) => handlePropUpdate(propName, newValue)"
				:required="config.required"
				:completions="(context: CompletionContext) => getCompletions(context, block?.getCompletions())"
				:showLineNumbers="false"
				class="overflow-hidden"
			/>
			<InlineInput
				v-else
				:label="propName"
				:type="config.inputType"
				:options="config.options"
				:required="config.required"
				:modelValue="getFormattedValue(propName)"
				@update:modelValue="(newValue) => handlePropUpdate(propName, newValue)"
				class="flex-1"
			/>
		</div>
	</div>
</template>

<script setup lang="ts">
import { computed, resolveComponent } from "vue"
import EmptyState from "@/components/EmptyState.vue"
import Block from "@/utils/block"

import InlineInput from "@/components/InlineInput.vue"
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

const props = defineProps<{
	block?: Block
	isTestingComponent?: boolean
}>()

const getCompletions = useStudioCompletions()
const canvasStore = useCanvasStore()

const componentInstance = computed(() => {
	if (!props.block?.componentName || props.block.isStudioComponent) return {}
	const component = resolveComponent(props.block?.componentName)
	if (typeof component === "string" || !component) {
		return {}
	}
	return component
})

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
	} else {
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

		if (isDynamicValue(config.modelValue) && ["select", "checkbox"].includes(config.inputType)) {
			config.inputType = "text"
		}
		filteredProps[propName] = config
	})

	return filteredProps
})

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
		}
	})
	return _props
}

const isCodeField = (inputType: string) => {
	return ["code", "html"].includes(inputType)
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
</script>
