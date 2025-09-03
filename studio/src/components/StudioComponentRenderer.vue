<template>
	<AppComponent v-if="block" :block="block" />
</template>

<script setup lang="ts">
import { provide, computed } from "vue"
import AppComponent from "@/components/AppComponent.vue"
import Block from "@/utils/block"
import useComponentStore from "@/stores/componentStore"
import { getDynamicValue, isDynamicValue } from "@/utils/helpers"

const props = defineProps<{
	studioComponent: Block
	evaluationContext: Object
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
	return { inputs: context }
})
provide("componentContext", componentContext)

const block = computed(() => componentStore.getNewStudioComponentInstance(props.studioComponent))
</script>
