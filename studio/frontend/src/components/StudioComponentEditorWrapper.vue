<template>
	<component :is="host" v-bind="testInputValues">
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
import { createComponentHost } from "@/utils/componentScript"

const props = defineProps<{
	studioComponent: Block
	breakpoint?: string
}>()

const componentEditorStore = useComponentEditorStore()
const componentStore = useComponentStore()
const componentBlock = computed(() => componentEditorStore.studioComponentBlock)
const canvasStore = useCanvasStore()
const componentId = computed(() => canvasStore.fragmentData.fragmentId ?? "")
const script = computed(() => componentStore.getComponentScript(componentId.value))

// The inputs of a component without a script change while it is edited, before they are saved.
const inputNames = computed(() =>
	componentEditorStore.componentInputs.map((input) => input.input_name).join(),
)
const host = computed(() => {
	if (script.value) return componentStore.getComponentHost(componentId.value)
	const names = inputNames.value.split(",").filter(Boolean)
	const inputs = names.map((input_name) => ({ input_name, type: "" }))
	return createComponentHost({ component_id: componentId.value, inputs }, null)
})

const testInputValues = computed(() => {
	const values = componentBlock.value?.getPropsAndAttributes() || {}
	if (script.value) return values
	componentEditorStore.componentInputs.forEach((input) => {
		if (!(input.input_name in values) && input.default !== undefined) {
			values[input.input_name] = input.default
		}
	})
	return values
})
</script>
