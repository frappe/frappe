<template>
	<IconButton
		ref="triggerButton"
		:icon="LucideCirclePlus"
		label="Set Dynamic Value"
		tooltipPlacement="left"
		class="mr-1"
		size="sm"
		tabIndex="-1"
		@click="showDynamicValueModal = !showDynamicValueModal"
	/>
	<DraggablePopup
		v-model="showDynamicValueModal"
		:container="triggerButton?.rootRef"
		placement="middle-right"
		:clickOutsideToClose="false"
		:placementOffset="20"
		:height="100"
		:width="600"
		v-if="showDynamicValueModal"
	>
		<template #header>
			<div class="text-base-semibold text-ink-gray-7">
				Set Dynamic Value
				<span v-if="propertyLabel" class="text-ink-gray-5">&middot; {{ propertyLabel }}</span>
			</div>
		</template>
		<template #content>
			<Code
				language="javascript"
				v-model="dynamicValue"
				:emitOnChange="true"
				:completions="(context: CompletionContext) => getCompletions(context, block?.getCompletions())"
			/>
			<div class="mt-2 flex items-center justify-between gap-2">
				<ErrorMessage v-if="error" :message="error" />
				<Button class="ml-auto" variant="solid" @click="setStyle">Set</Button>
			</div>
		</template>
	</DraggablePopup>
</template>

<script setup lang="ts">
import { computed, ref, watch } from "vue"
import { Button, ErrorMessage } from "frappe-ui"
import Code from "@/components/Code.vue"
import IconButton from "@/components/IconButton.vue"
import DraggablePopup from "@/components/DraggablePopup.vue"
import Block from "@/utils/block"
import { useStudioCompletions } from "@/utils/useStudioCompletions"
import { getExpressionError } from "@/utils/parseCode"
import type { CompletionContext } from "@codemirror/autocomplete"
import type { BlockProperty } from "@/components/ComponentStyles.vue"
import LucideCirclePlus from "~icons/lucide/circle-plus"

const props = defineProps<{ block?: Block; property: BlockProperty }>()
const emit = defineEmits<{
	(event: "update:modelValue", value: string): void
}>()

const triggerButton = ref<typeof IconButton | null>(null)
const showDynamicValueModal = ref(false)
const getCompletions = useStudioCompletions()
const propertyLabel = computed(() => props.property?.getProps?.()?.label as string)

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

const error = ref("")
watch(dynamicValue, () => (error.value = ""))

const setStyle = () => {
	// CSS values like var(--ink-red-5) must be quoted to be valid JS, flag them before saving
	error.value = getExpressionError(dynamicValue.value) || ""
	if (error.value) return

	emit("update:modelValue", dynamicValue.value)
	showDynamicValueModal.value = false
}
</script>
