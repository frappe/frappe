<template>
	<StudioComponent v-if="block" :block="block" :breakpoint="props.breakpoint" />
</template>

<script setup lang="ts">
import { provide, computed } from "vue"
import StudioComponent from "@/components/StudioComponent.vue"
import Block from "@/utils/block"
import useComponentStore from "@/stores/componentStore"
import { getBlockObject, getDynamicValue, isDynamicValue, isObjectEmpty } from "@/utils/helpers"

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
	const { componentId, componentName } = props.studioComponent
	const component = componentStore.componentMap.get(props.studioComponent.componentName)
	if (!component) {
		console.error(`Component with ID ${componentName} not found`)
		return
	}
	const blockOptions = getBlockObject(component)
	blockOptions.extendedFromComponent = componentName
	applyStudioComponentStyles(blockOptions)

	const newBlock = new Block(blockOptions)
	newBlock.initializeStudioComponent(componentName, componentId)
	return newBlock
})

const applyStudioComponentStyles = (blockOptions: any) => {
	const { baseStyles, mobileStyles, tabletStyles, rawStyles, visibilityCondition, classes } =
		props.studioComponent

	if (!isObjectEmpty(baseStyles)) blockOptions.baseStyles = { ...blockOptions.baseStyles, ...baseStyles }
	if (!isObjectEmpty(mobileStyles))
		blockOptions.mobileStyles = { ...blockOptions.mobileStyles, ...mobileStyles }
	if (!isObjectEmpty(tabletStyles))
		blockOptions.tabletStyles = { ...blockOptions.tabletStyles, ...tabletStyles }
	if (!isObjectEmpty(rawStyles)) blockOptions.rawStyles = { ...blockOptions.rawStyles, ...rawStyles }
	if (visibilityCondition) blockOptions.visibilityCondition = visibilityCondition
	if (classes?.length) blockOptions.classes = [...(blockOptions.classes || []), ...classes]
}
</script>
