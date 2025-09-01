<template>
	<StudioComponent v-if="block" :block="block" :breakpoint="props.breakpoint" />
</template>

<script setup lang="ts">
import { provide, computed } from "vue"
import StudioComponent from "@/components/StudioComponent.vue"
import Block from "@/utils/block"
import useComponentStore from "@/stores/componentStore"
import { getDynamicValue, isDynamicValue } from "@/utils/helpers"

const props = defineProps<{
	studioComponent: Block
	evaluationContext: Object
	breakpoint?: string
}>()
const componentStore = useComponentStore()

const componentContext = computed(() => {
	const context = { ...props.studioComponent.componentProps }
	const componentDoc = componentStore.getComponentDoc(props.studioComponent.componentName)
	if (componentDoc?.inputs) {
		componentDoc.inputs.forEach((input: any) => {
			if (!(input.input_name in context) && input.default !== undefined) {
				context[input.input_name] = input.default
			}

			Object.entries(context).forEach(([inputName, value]) => {
				if (isDynamicValue(value)) {
					context[inputName] = getDynamicValue(value, props.evaluationContext)
				}
			})
		})
	}
	return context
})
provide("componentContext", componentContext)

const block = computed(() => {
	const newBlock = componentStore.getNewStudioComponentInstance(props.studioComponent)
	if (!newBlock) {
		console.error(`Component with ID ${props.studioComponent.componentName} not found`)
		return
	}
	newBlock.initializeStudioComponent(props.studioComponent)
	return newBlock
})
</script>
