<template>
	<div class="flex select-none flex-col pb-16">
		<div v-if="props.block?.componentName && !props.block?.isRoot()" class="flex flex-col gap-3">
			<CollapsibleSection sectionName="Props">
				<div v-for="(config, propName) in componentProps" :key="propName">
					<InlineInput
						:label="propName"
						:type="config.inputType"
						:modelValue="config.modelValue"
						:options="config.options"
						:required="config.required"
						@update:modelValue="(val) => updateComponentProp(propName, val)"
					/>
				</div>
			</CollapsibleSection>

			<CollapsibleSection sectionName="Slots" v-if="componentSlots.length !== 0">
				<div
					v-if="!isObjectEmpty(block?.componentSlots)"
					v-for="(slot, name) in block?.componentSlots"
					:key="name"
					class="flex w-full flex-row justify-between"
				>
					<div class="flex w-full cursor-pointer items-start justify-between gap-2">
						<InlineInput
							:label="name"
							type="textarea"
							:modelValue="slot"
							@update:modelValue="(slotContent) => block?.updateSlot(name, slotContent)"
						/>
						<Button variant="outline" size="sm" icon="x" @click="block?.removeSlot(name)" />
					</div>
				</div>

				<EmptyState v-else message="No slots added" />

				<Autocomplete
					:options="componentSlots"
					@update:modelValue="(slot: SelectOption) => block?.addSlot(slot.value)"
				>
					<template #target="{ togglePopover }">
						<Button @click="togglePopover" class="w-full">Add</Button>
					</template>
				</Autocomplete>
			</CollapsibleSection>
		</div>

		<EmptyState v-else message="Select a block to edit properties" />
	</div>
</template>

<script setup lang="ts">
import { computed, watch, ref } from "vue"
import Block from "@/utils/block"

import { getComponentProps, getComponentSlots } from "@/utils/components"
import InlineInput from "@/components/InlineInput.vue"
import EmptyState from "@/components/EmptyState.vue"
import CollapsibleSection from "@/components/CollapsibleSection.vue"
import type { SelectOption } from "@/types"
import { isObjectEmpty } from "@/utils/helpers"

const props = defineProps<{
	block?: Block
}>()

const componentProps = computed(() => {
	if (!props.block || props.block.isRoot()) return {}
	const propConfig = getComponentProps(props.block.componentName) || {}
	if (!propConfig) return {}

	Object.entries(propConfig).forEach(([propName, config]) => {
		if (props.block?.componentProps[propName] === undefined) {
			const defaultValue = typeof config.default === "function" ? config.default() : config.default
			config.modelValue = defaultValue
		} else {
			config.modelValue = props.block.componentProps[propName]
		}
	})

	return propConfig
})

const updateComponentProp = (propName: string, newValue: any) => {
	props.block?.setProp(propName, newValue)
}

const componentSlots = ref<string[]>([])
watch(
	() => props.block?.componentName,
	async () => {
		if (!props.block || props.block.isRoot()) return
		const slots = await getComponentSlots(props.block.componentName)
		componentSlots.value = slots.map((slot) => slot.name)
	},
)
</script>
