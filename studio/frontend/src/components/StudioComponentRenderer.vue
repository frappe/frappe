<template>
	<component :is="host" v-if="host && block" v-bind="propValues" v-on="emittedListeners">
		<AppComponent :block="block" :listeners="rootListeners" />
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
// The component emits the events that its script declares. Every other event is a DOM event of its root block.
const emits = computed(() => componentStore.getComponentEmits(props.studioComponent.componentName))
const emittedListeners = computed(() => filterListeners((name) => isEmittedEvent(name, emits.value)))
const rootListeners = computed(() => filterListeners((name) => !isEmittedEvent(name, emits.value)))

function filterListeners(isIncluded: (name: string) => boolean) {
	return Object.fromEntries(Object.entries(props.listeners).filter(([name]) => isIncluded(name)))
}

const block = computed(() => componentStore.getNewStudioComponentInstance(props.studioComponent))
</script>
