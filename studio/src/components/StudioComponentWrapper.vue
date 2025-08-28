<template>
	<StudioComponent v-if="block" :block="block" :breakpoint="props.breakpoint" />
</template>

<script setup lang="ts">
import { watch, ref, provide, computed } from "vue"
import StudioComponent from "@/components/StudioComponent.vue"
import Block from "@/utils/block"
import useComponentStore from "@/stores/componentStore"
import { getBlockCopy } from "@/utils/helpers"

const props = defineProps<{
	studioComponent: Block
	breakpoint?: string
}>()
const block = ref<Block | undefined>()
const componentStore = useComponentStore()

const componentContext = computed(() => {
	const context = { ...props.studioComponent.componentProps }
	const componentDoc = componentStore.getComponentDoc(props.studioComponent.componentName)
	if (componentDoc?.inputs) {
		componentDoc.inputs.forEach((input: any) => {
			if (!(input.input_name in context) && input.default !== undefined) {
				context[input.input_name] = input.default
			}
		})
	}
	return context
})
provide("componentContext", componentContext)

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
