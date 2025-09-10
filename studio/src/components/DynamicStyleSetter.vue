<template>
	<Dropdown
		:options="[
			{
				label: 'Set Dynamic Value',
				onClick: () => {
					showDynamicValueModal = !showDynamicValueModal
				},
			},
		]"
	>
		<FeatherIcon
			ref="dropdownTrigger"
			name="plus-circle"
			class="mr-1 h-3 w-4 cursor-pointer select-none text-ink-gray-5 outline-none hover:text-ink-gray-9"
		/>
	</Dropdown>
	<DraggablePopup
		v-model="showDynamicValueModal"
		:container="dropdownTrigger?.$el"
		placement="middle-right"
		:clickOutsideToClose="false"
		:placementOffset="20"
		:height="100"
		:width="600"
		v-if="showDynamicValueModal"
	>
		<template #header><div class="text-base font-semibold text-gray-800">Set Dynamic Value</div></template>
		<template #content>
			<Code
				language="javascript"
				v-model="dynamicValue"
				:completions="(context: CompletionContext) => getCompletions(context, block?.getCompletions())"
				ref="styleEditor"
			/>
			<div class="mt-2 flex items-center justify-end gap-2">
				<Button variant="solid" @click="setStyle">Set</Button>
			</div>
		</template>
	</DraggablePopup>
</template>

<script setup lang="ts">
import { ref, watch } from "vue"
import { Dropdown, FeatherIcon } from "frappe-ui"
import Code from "@/components/Code.vue"
import Block from "@/utils/block"
import { useStudioCompletions } from "@/utils/useStudioCompletions"
import type { CompletionContext } from "@codemirror/autocomplete"
import type { BlockProperty } from "@/components/ComponentStyles.vue"

const props = defineProps<{ block?: Block; property: BlockProperty }>()
const emit = defineEmits<{
	(event: "update:modelValue", value: string): void
}>()

const dropdownTrigger = ref<typeof FeatherIcon | null>(null)
const showDynamicValueModal = ref(false)
const getCompletions = useStudioCompletions()

const dynamicValue = ref("")
watch(
	() => [props.property, props.property?.getValue?.()],
	() => {
		const value = props.property?.getValue?.() as string
		if (value) {
			if (!value.startsWith("{{")) {
				dynamicValue.value = `{{ '${value}' }}`
			} else {
				dynamicValue.value = value
			}
		} else {
			dynamicValue.value = "{{  }}"
		}
	},
	{ immediate: true, deep: true },
)

const styleEditor = ref()
const setStyle = () => {
	styleEditor.value?.emitEditorValue()
	emit("update:modelValue", dynamicValue.value)
	showDynamicValueModal.value = false
}
</script>
