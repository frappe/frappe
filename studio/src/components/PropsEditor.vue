<template>
	<template v-if="isObjectEmpty(componentProps)">
		<EmptyState v-if="showComponentEditorLink">
			<span>
				No editable properties yet. Add inputs inside the
				<button class="cursor-pointer underline" @click="openComponentEditor">component editor</button>
			</span>
		</EmptyState>
		<EmptyState v-else :message="`${block?.getBlockDescription()} has no editable properties`" />
	</template>
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
				:class="{ 'mt-1 self-start': isCodeField(config.inputType) || Boolean(config.editor) }"
				:isVariableBound="isVariableBound(config.modelValue)"
			/>

			<Code
				v-if="config.inputType === 'html'"
				:label="propName"
				language="html"
				:modelValue="getFormattedValue(propName)"
				:placeholder="isMixed(propName) ? 'Mixed' : undefined"
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
						:placeholder="isMixed(propName) ? 'Mixed' : undefined"
						@update:modelValue="(newValue) => handlePropUpdate(propName, newValue)"
						:required="config.required"
						:completions="dynamicValueCompletions"
						:overrideCompletions="true"
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
					<component
						v-else-if="config.editor && block"
						:is="config.editor"
						:label="propName"
						:block="block"
					/>
					<ArrayInput
						v-else-if="config.inputType === 'array'"
						:label="propName"
						:required="config.required"
						:modelValue="getFormattedValue(propName)"
						:emptyMessage="isMixed(propName) ? 'Mixed' : undefined"
						@update:modelValue="(newValue) => handlePropUpdate(propName, newValue)"
						:itemTypes="config.itemTypes"
					/>
				</div>
			</template>
			<component
				v-else-if="config.editor && block"
				:is="config.editor"
				:label="propName"
				:block="block"
				class="min-w-0 flex-1"
			/>
			<InlineInput
				v-else
				:label="propName"
				:type="config.inputType"
				:options="config.options"
				:required="config.required"
				:modelValue="getFormattedValue(propName)"
				:placeholder="isMixed(propName) ? 'Mixed' : undefined"
				@update:modelValue="(newValue) => handlePropUpdate(propName, newValue)"
				class="flex-1"
				v-bind="config.props"
			/>
		</div>
	</div>
</template>

<script setup lang="ts">
import { computed, ref } from "vue"
import { Button } from "frappe-ui"
import EmptyState from "@/components/EmptyState.vue"
import Block from "@/utils/block"

import InlineInput from "@/components/InlineInput.vue"
import ArrayInput from "@/components/ArrayInput.vue"
import { isObjectEmpty } from "@/utils/helpers"
import Code from "@/components/Code.vue"
import { useStudioCompletions, useDynamicValueCompletions } from "@/utils/useStudioCompletions"
import type { CompletionContext } from "@codemirror/autocomplete"
import useComponentStore from "@/stores/componentStore"
import { getComponentProps } from "@/utils/components"
import { isDynamicValue } from "@/utils/code"
import useCanvasStore from "@/stores/canvasStore"
import blockController from "@/utils/blockController"
import useComponentEditorStore from "@/stores/componentEditorStore"
import type { ComponentProp, ComponentProps } from "@/types"
import { ComponentInput } from "@/types/Studio/StudioComponent"
import DynamicValueSelector from "@/components/DynamicValueSelector.vue"
import useStudioStore from "@/stores/studioStore"
import useComponentInstance from "@/utils/useComponentInstance"

const props = defineProps<{
	block?: Block
	isTestingComponent?: boolean
	multiEdit?: boolean
}>()

const getCompletions = useStudioCompletions()
const getDynamicValueCompletions = useDynamicValueCompletions()
// created once: a fresh array here would make Code.vue rebuild its extensions on every re-render
const dynamicValueCompletions = getDynamicValueCompletions(() => props.block?.getCompletions())
const canvasStore = useCanvasStore()
const store = useStudioStore()

const componentInstance = useComponentInstance(() => props.block)

const showComponentEditorLink = computed(() => props.block?.isStudioComponent && !props.isTestingComponent)

const openComponentEditor = () => {
	if (!props.block) return
	useComponentEditorStore().editComponent(props.block.componentName)
}

const propConfigs = computed<ComponentProps>(() => {
	if (!props.block || props.block.isRoot()) return {}

	if (props.isTestingComponent) {
		const componentEditorStore = useComponentEditorStore()
		return getStudioComponentProps(componentEditorStore.componentInputs)
	}
	if (props.block.isStudioComponent) {
		const componentStore = useComponentStore()
		const componentDoc = componentStore.getComponentDoc(props.block.componentName)
		return componentDoc?.inputs ? getStudioComponentProps(componentDoc.inputs) : {}
	}
	if (componentInstance.value) {
		return getComponentProps(props.block.componentName, componentInstance.value)
	}
	return {}
})

const componentProps = computed(() => {
	const visibleProps: ComponentProps = {}

	Object.entries(propConfigs.value).forEach(([propName, config]) => {
		if (!isPropVisible(config)) return

		const propConfig = { ...config }
		const value = props.block?.componentProps[propName]
		propConfig.modelValue = value === undefined ? resolveDefault(config) : value

		if (
			(isDynamicValue(propConfig.modelValue) || isVariableBound(propConfig.modelValue)) &&
			!isCodeField(propConfig.inputType)
		) {
			propConfig.inputType = "code"
		}
		visibleProps[propName] = propConfig
	})

	return visibleProps
})

const isPropVisible = (config: ComponentProp, block = props.block) => {
	return config.condition ? config.condition(block?.componentProps) : true
}

const resolveDefault = (config: ComponentProp) => {
	return typeof config.default === "function" ? config.default() : config.default
}

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

function setProp(propName: string, value: any) {
	if (props.multiEdit) {
		blockController.setProp(propName, value)
	} else {
		props.block?.setProp(propName, value)
	}
	syncConditionalProps()
}

// sync conditional non-registered props like select -> options on FormControl
function syncConditionalProps() {
	const blocks = props.multiEdit ? blockController.getSelectedBlocks() : [props.block]
	blocks.forEach((block) => {
		if (!block) return
		Object.entries(propConfigs.value).forEach(([propName, config]) => {
			if (!config.condition) return
			if (!isPropVisible(config, block)) {
				block.removeProp(propName)
			} else if (block.componentProps[propName] === undefined) {
				const defaultValue = resolveDefault(config)
				if (defaultValue !== undefined) block.setProp(propName, defaultValue)
			}
		})
	})
}

function setDynamicValue(propName: string, varName: string, bindVariable: boolean) {
	if (bindVariable) {
		setProp(propName, { $type: "variable", name: varName })
	} else {
		setProp(propName, `{{ ${varName} }}`)
	}
}

const getRawValue = (propName: string) => {
	if (props.multiEdit) return blockController.getProp(propName)
	const value = props.block?.componentProps[propName]
	// unset props fall back to the component default, which is no longer stored on the block
	return value === undefined ? componentProps.value[propName]?.modelValue : value
}

const isMixed = (propName: string) => props.multiEdit && getRawValue(propName) === "Mixed"

const getFormattedValue = (propName: string) => {
	const value = getRawValue(propName)
	// mixed values across a multi-selection are surfaced via a placeholder, not a real value
	if (isMixed(propName)) return ""
	if (value?.$type === "variable") {
		return `{{ ${value.name} }}`
	}
	return value
}

const handlePropUpdate = (propName: string, newValue: any) => {
	setProp(propName, newValue)
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
