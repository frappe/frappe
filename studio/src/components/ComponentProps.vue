<template>
	<div class="flex select-none flex-col pb-16">
		<div v-if="props.block?.componentName && !props.block?.isRoot()" class="flex flex-col gap-3">
			<!-- props -->
			<div class="flex items-center justify-between text-sm font-medium">
				<h3 class="cursor-pointer text-base text-gray-900">Props</h3>
			</div>
			<div class="mb-4 mt-3 flex flex-col gap-3">
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

			<!-- slots -->
			<div class="mt-3 flex items-center justify-between text-sm font-medium">
				<h3 class="cursor-pointer text-base text-gray-900">Slots</h3>
				<Autocomplete
					:options="componentSlots"
					@update:modelValue="(slot: SelectOption) => block?.addSlot(slot.value)"
				>
					<template #target="{ togglePopover }">
						<Button @click="togglePopover" size="sm" variant="ghost" icon="plus" />
					</template>
				</Autocomplete>
			</div>

			<div class="mb-4 mt-3 flex flex-col gap-3" v-if="!isObjectEmpty(block?.componentSlots)">
				<div
					v-for="(slot, name) in block?.componentSlots"
					:key="name"
					class="flex w-full flex-row justify-between"
				>
					<div class="flex w-full cursor-pointer items-center justify-between gap-2">
						<div class="relative w-full">
							<InlineInput
								:label="name"
								type="textarea"
								:modelValue="getSlotContent(slot)"
								@update:modelValue="(slotContent) => block?.updateSlot(name, slotContent)"
								:disabled="Array.isArray(slot.slotContent)"
							/>
							<Badge
								v-if="Array.isArray(slot.slotContent)"
								variant="subtle"
								theme="blue"
								class="absolute left-2 top-8"
							>
								Component Tree
							</Badge>
						</div>
						<Button variant="outline" size="sm" icon="x" @click="block?.removeSlot(name)" />
					</div>
				</div>
			</div>

			<EmptyState v-else message="No slots added" />

			<!-- Visibility Condition -->
			<div class="mt-7 flex items-center justify-between text-sm font-medium">
				<h3 class="cursor-pointer text-base text-gray-900">Visibility Condition</h3>
			</div>
			<Code
				language="javascript"
				height="60px"
				:showLineNumbers="false"
				:completions="
					(context: CompletionContext) => getCompletions(context, block?.getRepeaterDataCompletions())
				"
				:modelValue="block?.visibilityCondition"
				@update:modelValue="blockController.setKeyValue('visibilityCondition', $event)"
			/>
		</div>

		<EmptyState v-else message="Select a block to edit properties" />
	</div>
</template>

<script setup lang="ts">
import { computed, watch, ref, resolveComponent } from "vue"
import { Autocomplete } from "frappe-ui"
import Block from "@/utils/block"

import { getComponentProps, getComponentSlots } from "@/utils/components"
import InlineInput from "@/components/InlineInput.vue"
import EmptyState from "@/components/EmptyState.vue"
import type { SelectOption, Slot } from "@/types"
import { isObjectEmpty } from "@/utils/helpers"
import useStudioStore from "@/stores/studioStore"
import IconButton from "@/components/IconButton.vue"
import Link2 from "~icons/lucide/link-2"
import Link2Off from "~icons/lucide/link-2-off"
import Code from "@/components/Code.vue"
import blockController from "@/utils/blockController"
import { useStudioCompletions } from "@/utils/useStudioCompletions"
import type { CompletionContext } from "@codemirror/autocomplete"

const props = defineProps<{
	block?: Block
}>()
const store = useStudioStore()
const getCompletions = useStudioCompletions()

const componentInstance = computed(() => {
	if (!props.block?.componentName) return {}
	const component = resolveComponent(props.block?.componentName)
	if (typeof component === "string" || !component) {
		return {}
	}
	return component
})

const componentProps = computed(() => {
	if (!props.block || props.block.isRoot()) return {}

	const propConfig = getComponentProps(props.block.componentName, componentInstance.value)
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

const componentSlots = ref<string[]>([])
watch(
	() => props.block?.componentName,
	async () => {
		await updateAvailableSlots()
	},
)

watch(
	() => props.block?.componentSlots,
	async () => {
		if (props.block?.isContainer()) return
		await updateAvailableSlots()
	},
	{ deep: true },
)

const updateAvailableSlots = async () => {
	if (!props.block || props.block.isRoot() || props.block.isContainer()) return

	const slots = await getComponentSlots(props.block.componentName)
	// filter out already added slots
	componentSlots.value = slots
		.filter((slot) => !(slot.name in (props.block?.componentSlots || [])))
		.map((slot) => slot.name)
}

const getSlotContent = (slot: Slot) => {
	if (!slot.slotContent) return ""
	else if (typeof slot.slotContent === "string") return slot.slotContent
	// hack to show the clear button for slot blocks
	return " "
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
