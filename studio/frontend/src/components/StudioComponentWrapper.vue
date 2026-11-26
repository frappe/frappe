<template>
	<component :is="host" v-if="host && block" v-bind="propValues">
		<StudioComponent :block="block" :breakpoint="props.breakpoint" />
	</component>
</template>

<script setup lang="ts">
import { computed } from "vue"
import StudioComponent from "@/components/StudioComponent.vue"
import Block from "@/utils/block"
import useComponentStore from "@/stores/componentStore"
import { useComponentPropValues } from "@/utils/useComponentPropValues"

const props = defineProps<{
	studioComponent: Block
	evaluationContext: Object
	breakpoint?: string
}>()
const componentStore = useComponentStore()

const host = computed(() => componentStore.getComponentHost(props.studioComponent.componentName))
const propValues = useComponentPropValues(
	() => props.studioComponent,
	() => props.evaluationContext,
)

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
