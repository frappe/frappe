<template>
	<StudioComponent v-if="rootBlock" :block="rootBlock" :breakpoint="props.breakpoint" />
</template>

<script setup lang="ts">
import { provide, computed } from "vue"
import StudioComponent from "@/components/StudioComponent.vue"
import Block from "@/utils/block"
import useComponentEditorStore from "@/stores/componentEditorStore"

const props = defineProps<{
	rootBlock: Block
	breakpoint?: string
}>()

const componentEditorStore = useComponentEditorStore()
const componentBlock = computed(() => componentEditorStore.studioComponentBlock!)

const componentContext = computed(() => {
	const context = { ...componentBlock.value.componentProps }
	componentEditorStore.componentInputs.forEach((input) => {
		if (!(input.input_name in context) && input.default !== undefined) {
			context[input.input_name] = input.default
		}
	})
	return context
})

provide("componentContext", componentContext)
</script>
