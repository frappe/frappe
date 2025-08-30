<template>
	<AppComponent v-if="block" :block="block" />
</template>

<script setup lang="ts">
import { provide, computed, watch, ref } from "vue"
import AppComponent from "@/components/AppComponent.vue"
import Block from "@/utils/block"
import useComponentStore from "@/stores/componentStore"
import { getBlockCopy, getDynamicValue, isDynamicValue } from "@/utils/helpers"

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
	return context
})
provide("componentContext", componentContext)

const block = ref<Block | undefined>()
const component = computed(() => componentStore.componentMap.get(props.studioComponent.componentName))
const loadComponentBlock = () => {
	const { componentId, componentName } = props.studioComponent
	if (!component.value) {
		console.error(`Component with ID ${componentName} not found`)
		return
	}
	block.value = getBlockCopy(component.value)
	block.value.initializeStudioComponent(componentName, componentId)
}

watch(() => props.studioComponent.componentId, loadComponentBlock, { immediate: true })

watch(
	() => component.value,
	() => {
		loadComponentBlock()
	},
	{ deep: true },
)
</script>
