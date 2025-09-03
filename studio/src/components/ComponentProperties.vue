<template>
	<div class="flex select-none flex-col pb-16">
		<EmptyState v-if="!block?.componentName || block?.isRoot()" message="Select a block to edit properties" />
		<div v-else class="flex flex-col gap-3">
			<!-- props -->
			<div class="flex items-center justify-between text-sm font-medium">
				<h3 class="cursor-pointer text-base text-gray-900">Props</h3>
			</div>
			<PropsEditor :block="block" />

			<!-- slots -->
			<div class="mt-3 flex items-center justify-between text-sm font-medium">
				<h3 class="cursor-pointer text-base text-gray-900">Slots</h3>
				<Autocomplete
					:options="componentSlots"
					@update:modelValue="(slot: SelectOption) => block?.addSlot(slot.value)"
					class="!w-auto"
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
				:completions="(context: CompletionContext) => getCompletions(context, block?.getCompletions())"
				:modelValue="block?.visibilityCondition"
				@update:modelValue="blockController.setKeyValue('visibilityCondition', $event)"
			/>
		</div>
	</div>
</template>

<script setup lang="ts">
import { watch, ref } from "vue"
import { Autocomplete } from "frappe-ui"
import Block from "@/utils/block"

import { getComponentSlots } from "@/utils/components"
import PropsEditor from "@/components/PropsEditor.vue"
import InlineInput from "@/components/InlineInput.vue"
import EmptyState from "@/components/EmptyState.vue"
import type { SelectOption, Slot } from "@/types"
import { isObjectEmpty } from "@/utils/helpers"
import Code from "@/components/Code.vue"
import blockController from "@/utils/blockController"
import { useStudioCompletions } from "@/utils/useStudioCompletions"
import type { CompletionContext } from "@codemirror/autocomplete"

const props = defineProps<{
	block?: Block
}>()
const getCompletions = useStudioCompletions()

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
</script>
