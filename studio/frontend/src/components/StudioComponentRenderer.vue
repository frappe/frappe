<template>
	<component :is="host" v-if="host && block" v-bind="propValues" v-on="emittedListeners">
		<AppComponent :block="block" />
	</component>
</template>

<script setup lang="ts">
import { computed } from "vue"
import AppComponent from "@/components/AppComponent.vue"
import Block from "@/utils/block"
import useComponentStore, { isEmittedEvent } from "@/stores/componentStore"
import { useComponentPropValues } from "@/utils/useComponentPropValues"

const props = defineProps<{
	studioComponent: Block
	evaluationContext: Object
	listeners: Record<string, Function | Function[]>
}>()
const componentStore = useComponentStore()

const host = computed(() => componentStore.getComponentHost(props.studioComponent.componentName))
const propValues = useComponentPropValues(
	() => props.studioComponent,
	() => props.evaluationContext,
)
// The listeners of every other event go on the root block, see getNewStudioComponentInstance.
const emittedListeners = computed(() => {
	const emits = componentStore.getComponentEmits(props.studioComponent.componentName)
	return Object.fromEntries(Object.entries(props.listeners).filter(([name]) => isEmittedEvent(name, emits)))
})

const block = computed(() => componentStore.getNewStudioComponentInstance(props.studioComponent))
</script>
