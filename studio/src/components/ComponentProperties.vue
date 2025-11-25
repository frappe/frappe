<template>
	<div class="flex select-none flex-col pb-16">
		<EmptyState v-if="!block?.componentName || block?.isRoot()" message="Select a block to edit properties" />
		<div v-else class="flex flex-col gap-3">
			<!-- props -->
			<SectionContainer title="Props" class="mb-4">
				<PropsEditor :block="block" />
			</SectionContainer>

			<!-- slots -->
			<SectionContainer title="Slots" class="mb-4">
				<template #actions>
					<Autocomplete
						:options="componentSlots"
						@update:modelValue="(slot: SelectOption) => block?.addSlot(slot.value)"
						class="!w-auto"
					>
						<template #target="{ togglePopover }">
							<Button @click="togglePopover" size="sm" variant="ghost" icon="plus" />
						</template>
					</Autocomplete>
				</template>

				<div class="flex flex-col gap-3" v-if="!isObjectEmpty(block?.componentSlots)">
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
			</SectionContainer>

			<!-- Attributes -->
			<SectionContainer title="Attributes" class="mb-4">
				<template #actions>
					<Button @click="attributesEditor?.addObjectKey()" size="sm" variant="ghost" icon="plus" />
				</template>
				<ObjectEditor
					ref="attributesEditor"
					:obj="blockController.getAttributes() || {}"
					@update:obj="(obj: Record<string, any>) => blockController.setAttributes(obj)"
					description="Pass additional HTML attributes or props not explicitly defined in the component"
					:showAddButton="false"
				/>
			</SectionContainer>

			<!-- Visibility Condition -->
			<SectionContainer title="Visibility Condition">
				<Code
					language="javascript"
					height="60px"
					:showLineNumbers="false"
					:completions="(context: CompletionContext) => getCompletions(context, block?.getCompletions())"
					:modelValue="block?.visibilityCondition"
					@update:modelValue="blockController.setKeyValue('visibilityCondition', $event)"
				/>
			</SectionContainer>
		</div>
	</div>
</template>

<script setup lang="ts">
import { watch, ref } from "vue"
import { Autocomplete } from "frappe-ui"
import Block from "@/utils/block"

import { getComponentSlots } from "@/utils/components"
import PropsEditor from "@/components/PropsEditor.vue"
import ObjectEditor from "@/components/ObjectEditor.vue"
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

const attributesEditor = ref<InstanceType<typeof ObjectEditor> | null>(null)

const componentSlots = ref<string[]>([])
watch(
	() => props.block?.componentName,
	() => updateAvailableSlots(),
)

watch(
	() => props.block?.componentSlots,
	() => {
		if (props.block?.isContainer()) return
		updateAvailableSlots()
	},
	{ deep: true },
)

const updateAvailableSlots = () => {
	if (!props.block || props.block.isRoot() || props.block.isContainer()) return

	const slots = getComponentSlots(props.block.componentName)
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
