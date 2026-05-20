<template>
	<div class="flex select-none flex-col pb-16" v-show="filteredSections?.length">
		<EmptyState v-if="!block?.componentName || block?.isRoot()" message="Select a block to edit properties" />
		<div v-else class="flex flex-col gap-3">
			<!-- props -->
			<SectionContainer title="Props" v-show="filteredSections.includes('props')">
				<PropsEditor ref="propsEditor" :block="block" />
			</SectionContainer>

			<!-- slots -->
			<SectionContainer title="Slots" v-show="filteredSections.includes('slots')">
				<template #actions>
					<Combobox
						:options="availableSlots"
						@update:modelValue="(slot: string) => block?.addSlot(slot)"
						align="end"
					>
						<template #trigger="{ togglePopover }">
							<Button @click="togglePopover" size="sm" variant="ghost" icon="lucide-plus" />
						</template>
					</Combobox>
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
							<Button variant="subtle" size="sm" icon="lucide-x" @click="block?.removeSlot(name)" />
						</div>
					</div>
				</div>
				<EmptyState v-else message="No slots added" />
			</SectionContainer>

			<!-- Visibility Condition -->
			<CollapsibleSection
				v-show="filteredSections.includes('visibility')"
				sectionName="Visibility Condition"
				:sectionCollapsed="sections.visibility?.collapsed"
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
				:sectionCollapsed="sections.attributes?.collapsed"
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
import { ref, computed, watchEffect } from "vue"
import { Combobox } from "frappe-ui"
import Block from "@/utils/block"

import { getComponentSlots } from "@/utils/components"
import PropsEditor from "@/components/PropsEditor.vue"
import ObjectEditor from "@/components/ObjectEditor.vue"
import InlineInput from "@/components/InlineInput.vue"
import EmptyState from "@/components/EmptyState.vue"
import type { Slot } from "@/types"
import { isObjectEmpty } from "@/utils/helpers"
import Code from "@/components/Code.vue"
import blockController from "@/utils/blockController"
import { useStudioCompletions } from "@/utils/useStudioCompletions"
import type { CompletionContext } from "@codemirror/autocomplete"
import useStudioStore from "@/stores/studioStore"

const props = defineProps<{
	block?: Block
}>()
const getCompletions = useStudioCompletions()
const studioStore = useStudioStore()

const attributesEditor = ref<InstanceType<typeof ObjectEditor> | null>(null)
const propsEditor = ref<InstanceType<typeof PropsEditor> | null>(null)

const componentSlots = ref<string[]>([])
const availableSlots = computed(() => {
	return componentSlots.value?.filter((slot) => !(slot in (props.block?.componentSlots || {})))
})
watchEffect(async () => {
	if (!props.block || props.block.isRoot() || props.block.isContainer()) {
		componentSlots.value = []
		return
	}
	const slots = await getComponentSlots(props.block.componentName, props.block.isCustomVueComponent)
	componentSlots.value = slots.map((slot) => slot.name)
})

const getSlotContent = (slot: Slot) => {
	if (!slot.slotContent) return ""
	else if (typeof slot.slotContent === "string") return slot.slotContent
	// hack to show the clear button for slot blocks
	return " "
}

const sections: Record<string, { condition?: any; collapsed?: any; searchKeyWords: string }> = {
	props: {
		condition: computed(() => !props.block?.isContainer()),
		searchKeyWords: "Props, Properties, Inputs",
	},
	slots: {
		condition: computed(() => !isObjectEmpty(componentSlots.value)),
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
