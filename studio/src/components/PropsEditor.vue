<template>
	<EmptyState
		v-if="isObjectEmpty(componentProps)"
		:message="`${block?.getBlockDescription()} has no editable properties`"
	/>
	<div v-else class="mb-4 mt-3 flex flex-col gap-3">
		<div v-for="(config, propName) in componentProps" :key="propName">
			<div class="flex w-full items-center gap-2">
				<Code
					v-if="config.inputType === 'code'"
					:label="propName"
					language="javascript"
					:modelValue="config.modelValue"
					@update:modelValue="(newValue) => props.block?.setProp(propName, newValue)"
					:required="config.required"
					:completions="
						(context: CompletionContext) => getCompletions(context, block?.getRepeaterDataCompletions())
					"
					:showLineNumbers="false"
				/>
				<InlineInput
					v-else-if="propName !== 'modelValue'"
					:label="propName"
					:type="config.inputType"
					:options="config.options"
					:required="config.required"
					:modelValue="config.modelValue"
					@update:modelValue="(newValue) => props.block?.setProp(propName, newValue)"
					class="flex-1"
				/>
				<InlineInput
					v-else-if="propName === 'modelValue'"
					:label="propName"
					:type="config.inputType"
					:options="config.options"
					:required="config.required"
					v-model="boundValue"
					class="flex-1"
				/>
				<Autocomplete
					v-if="propName === 'modelValue'"
					:options="store.variableOptions"
					placeholder="Select variable"
					@update:modelValue="(variable: SelectOption) => bindVariable(propName, variable.value)"
					class="!w-auto"
				>
					<template #target="{ togglePopover }">
						<IconButton
							:icon="isVariableBound(config.modelValue) ? Link2Off : Link2"
							:label="
								isVariableBound(config.modelValue) ? 'Disable sync with variable' : 'Sync with variable'
							"
							placement="bottom"
							@click="
								() => {
									if (isVariableBound(config.modelValue)) {
										unbindVariable(propName)
									} else {
										togglePopover()
									}
								}
							"
						/>
					</template>
				</Autocomplete>
			</div>
		</div>
	</div>
</template>

<script setup lang="ts">
import { computed, resolveComponent } from "vue"
import EmptyState from "@/components/EmptyState.vue"
import { Autocomplete } from "frappe-ui"
import Block from "@/utils/block"

import InlineInput from "@/components/InlineInput.vue"
import type { SelectOption } from "@/types"
import { isObjectEmpty } from "@/utils/helpers"
import useStudioStore from "@/stores/studioStore"
import IconButton from "@/components/IconButton.vue"
import Link2 from "~icons/lucide/link-2"
import Link2Off from "~icons/lucide/link-2-off"
import Code from "@/components/Code.vue"
import { useStudioCompletions } from "@/utils/useStudioCompletions"
import type { CompletionContext } from "@codemirror/autocomplete"
import { useComponentStore } from "@/stores/componentStore"
import { getComponentProps } from "@/utils/components"
import useComponentEditorStore from "@/stores/componentEditorStore"
import type { ComponentProps } from "@/types"
import { ComponentInput } from "@/types/Studio/StudioComponent"

const props = defineProps<{
	block?: Block
	isEditingComponent?: boolean
}>()

const store = useStudioStore()
const getCompletions = useStudioCompletions()

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
	if (props.isEditingComponent) {
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

	Object.entries(propConfig).forEach(([propName, config]) => {
		if (props.block?.componentProps[propName] === undefined) {
			const defaultValue = typeof config.default === "function" ? config.default() : config.default
			config.modelValue = defaultValue
		} else {
			config.modelValue = props.block.componentProps[propName]
		}

		if (isVariableBound(config.modelValue)) {
			config.inputType = "text"
		}
	})

	return propConfig
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

// variable binding
const boundValue = computed({
	get() {
		const modelValue = props.block?.componentProps.modelValue
		if (modelValue?.$type === "variable") {
			return `{{ ${modelValue.name} }}`
		}
		return modelValue
	},
	set(newValue) {
		props.block?.setProp("modelValue", newValue)
	},
})

const isVariableBound = (value: any) => {
	return value?.$type === "variable" ? value.name : null
}

const bindVariable = (propName: string, varName: string) => {
	props.block?.setProp(propName, { $type: "variable", name: varName })
}

const unbindVariable = (propName: string) => {
	props.block?.setProp(propName, "")
}
</script>
