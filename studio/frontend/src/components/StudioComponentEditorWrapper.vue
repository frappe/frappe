<template>
	<component :is="host" v-if="host" v-bind="previewValues">
		<StudioComponent :block="studioComponent" :breakpoint="props.breakpoint" />
	</component>
</template>

<script setup lang="ts">
import { computed } from "vue"
import StudioComponent from "@/components/StudioComponent.vue"
import Block from "@/utils/block"
import useComponentEditorStore from "@/stores/componentEditorStore"
import useComponentStore from "@/stores/componentStore"
import useCanvasStore from "@/stores/canvasStore"

const props = defineProps<{
	studioComponent: Block
	breakpoint?: string
}>()

const componentEditorStore = useComponentEditorStore()
const componentStore = useComponentStore()
const componentBlock = computed(() => componentEditorStore.studioComponentBlock)
const canvasStore = useCanvasStore()
const componentId = computed(() => canvasStore.fragmentData.fragmentId ?? "")
const host = computed(() => componentStore.getComponentHost(componentId.value))

const previewValues = computed(() => {
	const values = componentBlock.value?.getPropsAndAttributes() || {}
	// Vue applies the defaults of a script's props
	if (componentStore.getComponentScript(componentId.value)) return values
	componentEditorStore.declaredProps.forEach((input) => {
		if (!(input.input_name in values) && input.default !== undefined) {
			values[input.input_name] = input.default
		}
	})
	return values
})
</script>
