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
		<IconButton
			ref="dropdownTrigger"
			:icon="LucideCirclePlus"
			placement="bottom"
			class="mr-1"
			size="sm"
			tabIndex="-1"
		/>
	</Dropdown>
	<DraggablePopup
		v-model="showDynamicValueModal"
		:container="dropdownTrigger?.rootRef"
		placement="middle-right"
		:clickOutsideToClose="false"
		:placementOffset="20"
		:height="100"
		:width="600"
		v-if="showDynamicValueModal"
	>
		<template #header><div class="text-base-semibold text-ink-gray-7">Set Dynamic Value</div></template>
		<template #content>
			<Code
				language="javascript"
				v-model="dynamicValue"
				:emitOnChange="true"
				:completions="(context: CompletionContext) => getCompletions(context, block?.getCompletions())"
			/>
			<div class="mt-2 flex items-center justify-end gap-2">
				<Button variant="solid" @click="setStyle">Set</Button>
			</div>
		</template>
	</DraggablePopup>
</template>

<script setup lang="ts">
import { ref, watch } from "vue"
import { Dropdown } from "frappe-ui"
import Code from "@/components/Code.vue"
import IconButton from "@/components/IconButton.vue"
import Block from "@/utils/block"
import { useStudioCompletions } from "@/utils/useStudioCompletions"
import type { CompletionContext } from "@codemirror/autocomplete"
import type { BlockProperty } from "@/components/ComponentStyles.vue"
import LucideCirclePlus from "~icons/lucide/circle-plus"

const props = defineProps<{ block?: Block; property: BlockProperty }>()
const emit = defineEmits<{
	(event: "update:modelValue", value: string): void
}>()

const dropdownTrigger = ref<typeof IconButton | null>(null)
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

const setStyle = () => {
	emit("update:modelValue", dynamicValue.value)
	showDynamicValueModal.value = false
}
</script>
