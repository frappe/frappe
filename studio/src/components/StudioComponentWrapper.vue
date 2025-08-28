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
	componentBlock: Block
	breakpoint?: string
}>()
const block = ref<Block | undefined>()
const componentStore = useComponentStore()

const componentContext = computed(() => {
	const context = { ...props.componentBlock.componentProps }
	const componentDoc = componentStore.getComponentDoc(props.componentBlock.componentName)
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

watch(
	() => props.componentBlock.componentId,
	async () => {
		const { componentId, componentName } = props.componentBlock
		const component = await componentStore.getComponent(componentName)
		if (!component) {
			console.error(`Component with ID ${componentName} not found`)
			return
		}
		block.value = getBlockCopy(component)
		block.value.initializeStudioComponent(componentName, componentId)
	},
	{ immediate: true },
)
</script>
