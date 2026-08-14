<template>
	<div class="flex select-none flex-col pb-16" v-if="filteredSections.length">
		<EmptyState v-if="mixedTypeSelection" message="Select blocks of the same component to edit properties" />
		<EmptyState v-else-if="!block?.componentName" message="Select a block to edit properties" />
		<div v-else class="flex flex-col gap-3">
			<!-- props -->
			<SectionContainer title="Props" v-show="filteredSections.includes('props')">
				<PropsEditor ref="propsEditor" :block="block" :multiEdit="multipleBlocksSelected" />
			</SectionContainer>

			<!-- slots -->
			<SectionContainer title="Slots" v-show="filteredSections.includes('slots') && !multipleBlocksSelected">
				<template #actions>
					<Combobox
						:key="Object.keys(block?.componentSlots || {}).length"
						:options="availableSlotOptions"
						:allowCustomValue="true"
						placeholder="Search or add a slot"
						@update:modelValue="(slotName: string) => addSlot(slotName)"
						align="end"
					>
						<template #trigger="{ togglePopover }">
							<Button @click="togglePopover" size="sm" variant="ghost" icon="lucide-plus" />
						</template>
					</Combobox>
				</template>

				<div v-if="!isObjectEmpty(block?.componentSlots)" class="flex flex-col gap-1">
					<div
						v-for="(slot, slotName) in block?.componentSlots"
						:key="slotName"
						class="flex w-full cursor-pointer items-center justify-between gap-1 rounded py-0.5"
						@click="selectSlot(slotName)"
					>
						<div class="flex min-w-0 items-center gap-1.5">
							<Tooltip
								placement="left"
								:hoverDelay="0"
								:text="isDynamicSlot(slotName) ? 'Dynamic slot' : 'Standard slot'"
							>
								<span class="inline-flex shrink-0">
									<component
										:is="isDynamicSlot(slotName) ? LucideZap : LucideHash"
										class="size-3 text-ink-gray-4"
									/>
								</span>
							</Tooltip>
							<span class="truncate text-sm text-ink-gray-5">{{ slotName }}</span>
						</div>
						<div class="flex shrink-0 items-center gap-2">
							<Badge
								theme="gray"
								variant="outline"
								class="text-sm text-ink-gray-5"
								v-if="getSlotSummary(slotName)"
							>
								{{ getSlotSummary(slotName) }}
							</Badge>
							<Button variant="ghost" size="sm" icon="lucide-x" @click.stop="removeSlot(slotName)" />
						</div>
					</div>
				</div>
				<EmptyState v-else message="No slots added" />
			</SectionContainer>

			<!-- Visibility Condition -->
			<CollapsibleSection
				v-show="filteredSections.includes('visibility')"
				sectionName="Visibility Condition"
				:sectionCollapsed="toValue(sections.visibility?.collapsed) && !studioStore.propertyFilter"
			>
				<template #actions>
					<Button
						v-if="block?.hasVisibilityCondition()"
						title="Toggle visibility condition"
						variant="ghost"
						@click.stop="block?.toggleVisibilityCondition()"
					>
						<FeatherIcon :name="block.visibilityCondition ? 'zap' : 'zap-off'" class="h-3 w-3" />
					</Button>
				</template>
				<Code
					language="javascript"
					height="60px"
					:showLineNumbers="false"
					:completions="(context: CompletionContext) => getCompletions(context, block?.getCompletions())"
					:modelValue="block?.visibilityCondition || block?.__lastVisibilityCondition"
					:readonly="!!block.__lastVisibilityCondition"
					@update:modelValue="blockController.setKeyValue('visibilityCondition', $event)"
				/>
			</CollapsibleSection>

			<!-- attributes -->
			<CollapsibleSection
				v-show="filteredSections.includes('attributes')"
				sectionName="Attributes"
				:sectionCollapsed="toValue(sections.attributes?.collapsed) && !studioStore.propertyFilter"
			>
				<ObjectEditor
					ref="attributesEditor"
					:obj="blockController.getAttributes() || {}"
					@update:obj="(obj: Record<string, any>) => blockController.setAttributes(obj)"
					description="Pass additional HTML attributes or props that are not explicitly defined in the component"
				/>
			</CollapsibleSection>
		</div>
	</div>
</template>

<script setup lang="ts">
import { ref, computed, toValue, watchEffect } from "vue"
import { Combobox, Button, Tooltip, Badge, FeatherIcon } from "frappe-ui"
import Block from "@/utils/block"
import { getComponentSlots } from "@/utils/components"
import PropsEditor from "@/components/PropsEditor.vue"
import ObjectEditor from "@/components/ObjectEditor.vue"
import EmptyState from "@/components/EmptyState.vue"
import SectionContainer from "@/components/SectionContainer.vue"
import CollapsibleSection from "@/components/CollapsibleSection.vue"
import { confirm, isObjectEmpty } from "@/utils/helpers"
import Code from "@/components/Code.vue"
import blockController from "@/utils/blockController"
import { useStudioCompletions } from "@/utils/useStudioCompletions"
import type { CompletionContext } from "@codemirror/autocomplete"
import useStudioStore from "@/stores/studioStore"
import useCanvasStore from "@/stores/canvasStore"

import LucideZap from "~icons/lucide/zap"
import LucideHash from "~icons/lucide/hash"

const props = defineProps<{
	block?: Block
}>()
const getCompletions = useStudioCompletions()
const studioStore = useStudioStore()
const canvasStore = useCanvasStore()

const multipleBlocksSelected = computed(() => blockController.multipleBlocksSelected())
const mixedTypeSelection = computed(
	() => multipleBlocksSelected.value && !blockController.selectedBlocksHaveSameType(),
)

const attributesEditor = ref<InstanceType<typeof ObjectEditor> | null>(null)
const propsEditor = ref<InstanceType<typeof PropsEditor> | null>(null)

const declaredSlots = ref<string[]>([])

watchEffect(async () => {
	if (!props.block || props.block.isRoot() || props.block.isContainer()) {
		declaredSlots.value = []
		return
	}
	const slots = await getComponentSlots(props.block.componentName, props.block.isCustomVueComponent)
	declaredSlots.value = slots.map((slot) => slot.name)
})

type SlotOption = { label: string; value: string }
const availableSlotOptions = computed<SlotOption[]>(() =>
	declaredSlots.value
		.filter((name) => !props.block?.getSlot(name))
		.map((name) => ({ label: name, value: name })),
)

const addSlot = (slotName: string) => {
	if (!slotName) return
	slotName = slotName?.trim()
	if (slotName && !props.block?.getSlot(slotName)) {
		props.block?.addSlot(slotName)
	}
}

const isDynamicSlot = (slotName: string) => !declaredSlots.value.includes(slotName)

const getSlotSummary = (slotName: string) => {
	const count = props.block?.getSlot(slotName)?.slotContent.length
	if (!count) return ""
	return count === 1 ? "1 block" : `${count} blocks`
}

const removeSlot = async (slotName: string) => {
	const count = props.block?.getSlot(slotName)?.slotContent.length || 0
	if (
		count &&
		!(await confirm(`${slotName} slot has ${count === 1 ? "1 block" : `${count} blocks`}. Remove it?`))
	) {
		return
	}
	props.block?.removeSlot(slotName)
}

const selectSlot = (slotName: string) => {
	const slot = props.block?.getSlot(slotName)
	if (slot) canvasStore.activeCanvas?.selectSlot(slot)
}

const sections: Record<string, { condition?: any; collapsed?: any; searchKeyWords: string }> = {
	props: {
		condition: computed(() => !props.block?.isContainer()),
		searchKeyWords: "Props, Properties, Inputs",
	},
	slots: {
		condition: computed(() => declaredSlots.value.length > 0 || !isObjectEmpty(props.block?.componentSlots)),
		searchKeyWords: "Slots, Slot, Component Slots, Component Slot, Customize Template",
	},
	visibility: {
		collapsed: computed(() => !props.block?.hasVisibilityCondition()),
		searchKeyWords:
			"Condition, Visibility, VisibilityCondition, Visibility Condition, show, hide, display, hideIf, showIf",
	},
	attributes: {
		collapsed: computed(() => isObjectEmpty(blockController.getAttributes())),
		searchKeyWords: "Attributes, CustomAttributes, Custom Attributes, HTML Attributes, Data Attributes",
	},
}

const filteredSections = computed(() => {
	let filtered = Object.keys(sections).filter((sectionName) => {
		const hasCondition = sections[sectionName]?.condition
		if (hasCondition && !hasCondition.value) return false

		const filter = studioStore.propertyFilter?.toLowerCase()
		if (!filter) return true

		if (sectionName === "props" && propsEditor.value?.hasFilteredProps) {
			return true
		}
		return sections[sectionName]?.searchKeyWords.toLowerCase().includes(filter) || false
	})
	return filtered
})
</script>
