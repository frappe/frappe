<template>
	<div class="flex select-none flex-col pb-16">
		<div v-if="props.block?.componentName && !props.block?.isRoot()" class="flex flex-col gap-3">
			<!-- props -->
			<div class="flex items-center justify-between text-sm font-medium">
				<h3 class="cursor-pointer text-base text-gray-900">Props</h3>
			</div>
			<div class="mb-4 mt-3 flex flex-col gap-3">
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
					<div class="flex w-full cursor-pointer items-start justify-between gap-2">
						<div class="relative w-full">
							<InlineInput
								:label="name"
								type="textarea"
								:modelValue="getSlotContent(slot)"
								@update:modelValue="(slotContent) => block?.updateSlot(name, slotContent)"
							/>
							<Badge
								v-if="Array.isArray(slot.slotContent)"
								variant="subtle"
								theme="blue"
								class="absolute right-5 top-4 -translate-y-1/2"
							>
								Component Tree
							</Badge>
						</div>
						<Button variant="outline" size="sm" icon="x" @click="block?.removeSlot(name)" />
					</div>
				</div>
			</div>

			<EmptyState v-else message="No slots added" />
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
import type { SelectOption, Slot } from "@/types"
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
		await updateAvailableSlots()
	},
)

watch(
	() => props.block?.componentSlots,
	async () => {
		await updateAvailableSlots()
	},
	{ deep: true },
)

const updateAvailableSlots = async () => {
	if (!props.block || props.block.isRoot()) return

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
</script>
