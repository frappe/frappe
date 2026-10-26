<template>
	<SectionContainer title="Variants">
		<div class="mt-3 flex flex-col gap-3">
			<InlineInput
				label="Editing"
				type="select"
				:options="optionChoices"
				:modelValue="String(shownIndex)"
				@update:modelValue="(value: string) => setEditorVariantChoice(block.componentId, Number(value))"
			/>
			<Button
				variant="subtle"
				size="sm"
				label="Keep this option"
				:disabled="options.length < 2"
				@click="keepShownOption"
			/>
		</div>
	</SectionContainer>
</template>

<script setup lang="ts">
import { computed } from "vue"
import { Button, dialog, toast } from "frappe-ui"
import Block from "@/utils/block"
import InlineInput from "@/components/InlineInput.vue"
import SectionContainer from "@/components/SectionContainer.vue"
import useCanvasStore from "@/stores/canvasStore"
import { getEditorVariantChoice, keepDialogText, parseVariantOptions, setEditorVariantChoice } from "@/utils/variants"

const props = defineProps<{ block: Block }>()

const options = computed(() => parseVariantOptions(props.block.componentProps.options))
const optionChoices = computed(() =>
	options.value.map((option, index) => ({ label: option, value: String(index) })),
)
const shownIndex = computed(() =>
	Math.min(getEditorVariantChoice(props.block.componentId), Math.max(options.value.length - 1, 0)),
)

function keepShownOption() {
	const kept = options.value[shownIndex.value] || `Option ${shownIndex.value + 1}`
	dialog.confirm({
		...keepDialogText(options.value, shownIndex.value),
		confirmLabel: "Keep",
		onConfirm: async () => {
			// a local canvas edit, unlike the viewer pill's server call, so undo and
			// autosave treat it like any other block change
			const parent = props.block.getParentBlock()
			const chosen = props.block.children[shownIndex.value]
			if (!parent || !chosen) throw new Error("The shown option has no block to keep")
			const index = parent.getChildIndex(props.block)
			const keep = () => {
				parent.removeChild(props.block)
				parent.insertChild(chosen, index, props.block.parentSlotName)
				chosen.selectBlock()
			}
			// batched, so selecting the kept block doesn't bleed into the pre-keep
			// history record and undo reselects the Variants block
			const history = useCanvasStore().activeCanvas?.history
			history ? history.batch(keep) : keep()
			toast.success(`Kept "${kept}"`)
		},
	})
}
</script>
