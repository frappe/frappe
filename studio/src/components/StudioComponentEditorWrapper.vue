<template>
	<StudioComponent v-if="studioComponent" :block="studioComponent" :breakpoint="props.breakpoint" />
</template>

<script setup lang="ts">
import { provide, computed } from "vue"
import StudioComponent from "@/components/StudioComponent.vue"
import Block from "@/utils/block"
import useComponentEditorStore from "@/stores/componentEditorStore"

const props = defineProps<{
	studioComponent: Block
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
	return { inputs: context }
})

provide("componentContext", componentContext)
</script>
