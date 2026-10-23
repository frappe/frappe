<template>
	<StudioComponentRenderer :studioComponent="block" :evaluationContext="{}" />
</template>

<script setup lang="ts">
import { computed, useAttrs } from "vue"
import Block from "@/utils/block"
import useComponentStore from "@/stores/componentStore"
import StudioComponentRenderer from "@/components/StudioComponentRenderer.vue"

defineOptions({ inheritAttrs: false })

const props = defineProps<{ componentId: string }>()
const hostProps = useAttrs()
const componentStore = useComponentStore()

const block = computed(
	() =>
		new Block({
			componentName: props.componentId,
			isStudioComponent: true,
			componentProps: getInputs(),
		}),
)

function getInputs() {
	const doc = (hostProps.doc || {}) as Record<string, any>
	const inputs: Record<string, any> = {}
	for (const { input_name } of componentStore.getComponentDoc(props.componentId)?.inputs || []) {
		if (input_name in hostProps) inputs[input_name] = hostProps[input_name]
		else if (input_name in doc) inputs[input_name] = doc[input_name]
	}
	return inputs
}
</script>
