<template>
	<div class="flex select-none flex-col pb-16" v-show="filteredSections?.length">
		<EmptyState v-if="mixedTypeSelection" message="Select blocks of the same component to edit properties" />
		<EmptyState v-else-if="!block?.componentName" message="Select a block to edit properties" />
		<div v-else class="flex flex-col gap-3">
			<!-- props -->
			<SectionContainer title="Props" v-show="filteredSections.includes('props')">
				<PropsEditor ref="propsEditor" :block="block" :multiEdit="multipleBlocksSelected" />
			</SectionContainer>

			<!-- slots -->
			<SectionContainer title="Slots" v-show="filteredSections.includes('slots') && !multipleBlocksSelected">
				<div class="flex flex-col gap-1">
					<div
						v-for="slotName in slotNames"
						:key="slotName"
						class="flex w-full cursor-pointer items-center justify-between gap-2 rounded px-1 py-0.5 hover:bg-surface-gray-2"
						@click="selectSlot(slotName)"
					>
						<span
							class="truncate text-base"
							:class="isDynamicSlot(slotName) ? 'italic text-ink-gray-5' : 'text-ink-gray-5'"
							:title="isDynamicSlot(slotName) ? 'Studio cannot verify this slot name' : slotName"
						>
							{{ slotName }}
						</span>
						<div class="flex shrink-0 items-center gap-2">
							<span class="text-sm text-ink-gray-5">{{ getSlotSummary(slotName) }}</span>
							<Switch
								size="sm"
								:modelValue="block?.getSlot(slotName) !== undefined"
								@update:modelValue="toggleSlot(slotName)"
								@click.stop
							/>
						</div>
					</div>

					<TextInput
						v-if="addingDynamicSlot"
						ref="dynamicSlotInput"
						size="sm"
						variant="ghost"
						placeholder="Slot name"
						v-model="dynamicSlotName"
						@keydown.enter="addDynamicSlot"
						@keydown.esc="cancelAddingDynamicSlot"
						@blur="addDynamicSlot"
					/>
					<button
						v-else
						class="flex items-center gap-1 px-1 py-0.5 text-sm text-ink-gray-4 hover:text-ink-gray-6"
						@click="startAddingDynamicSlot"
					>
						<LucidePlus class="h-3 w-3" />
						Dynamic slot
					</button>
				</div>
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
import { ref, computed, nextTick, watchEffect } from "vue"
import { Switch, TextInput } from "frappe-ui"
import Block from "@/utils/block"

import { getComponentSlots } from "@/utils/components"
import PropsEditor from "@/components/PropsEditor.vue"
import ObjectEditor from "@/components/ObjectEditor.vue"
import EmptyState from "@/components/EmptyState.vue"
import { confirm, isObjectEmpty } from "@/utils/helpers"
import Code from "@/components/Code.vue"
import blockController from "@/utils/blockController"
import { useStudioCompletions } from "@/utils/useStudioCompletions"
import type { CompletionContext } from "@codemirror/autocomplete"
import useStudioStore from "@/stores/studioStore"
import useCanvasStore from "@/stores/canvasStore"
import LucidePlus from "~icons/lucide/plus"

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

// slots the component declares, plus any dynamic ones already added to this block
const declaredSlots = ref<string[]>([])
const slotNames = computed(() => {
	const added = Object.keys(props.block?.componentSlots || {})
	return [...declaredSlots.value, ...added.filter((name) => !declaredSlots.value.includes(name))]
})

watchEffect(async () => {
	if (!props.block || props.block.isRoot() || props.block.isContainer()) {
		declaredSlots.value = []
		return
	}
	const slots = await getComponentSlots(props.block.componentName, props.block.isCustomVueComponent)
	declaredSlots.value = slots.map((slot) => slot.name)
})

// a slot named at runtime by the component (e.g. Select's per-option slots) cannot be verified
const isDynamicSlot = (slotName: string) => !declaredSlots.value.includes(slotName)

const getSlotSummary = (slotName: string) => {
	const count = props.block?.getSlot(slotName)?.slotContent.length
	if (count === undefined) return ""
	if (!count) return ""
	return count === 1 ? "1 block" : `${count} blocks`
}

// the switch controls whether the slot exists — and so whether it is droppable on the canvas
const toggleSlot = async (slotName: string) => {
	const slot = props.block?.getSlot(slotName)
	if (!slot) return props.block?.addSlot(slotName)

	const count = slot.slotContent.length
	if (
		count &&
		!(await confirm(`#${slotName} has ${count === 1 ? "1 block" : `${count} blocks`}. Remove it?`))
	) {
		return
	}
	props.block?.removeSlot(slotName)
}

const selectSlot = (slotName: string) => {
	const slot = props.block?.getSlot(slotName)
	if (slot) canvasStore.activeCanvas?.selectSlot(slot)
}

const addingDynamicSlot = ref(false)
const dynamicSlotName = ref("")
const dynamicSlotInput = ref<{ el: HTMLInputElement } | null>(null)

const startAddingDynamicSlot = async () => {
	addingDynamicSlot.value = true
	await nextTick()
	dynamicSlotInput.value?.el?.focus()
}

const cancelAddingDynamicSlot = () => {
	dynamicSlotName.value = ""
	addingDynamicSlot.value = false
}

const addDynamicSlot = () => {
	const slotName = dynamicSlotName.value.trim()
	if (slotName && !props.block?.getSlot(slotName)) {
		props.block?.addSlot(slotName)
	}
	dynamicSlotName.value = ""
	addingDynamicSlot.value = false
}

const sections: Record<string, { condition?: any; collapsed?: any; searchKeyWords: string }> = {
	props: {
		condition: computed(() => !props.block?.isContainer()),
		searchKeyWords: "Props, Properties, Inputs",
	},
	slots: {
		condition: computed(() => slotNames.value.length > 0),
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
