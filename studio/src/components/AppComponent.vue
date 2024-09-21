<template>
	<component
		ref="componentRef"
		:is="components.getComponent(block.componentName)"
		v-bind="componentProps"
		:data-component-id="block.componentId"
		:style="styles"
	>
		<AppComponent v-for="child in block?.children" :key="child.componentId" :block="child" />
	</component>
</template>

<script setup>
import Block from "@/utils/block"
import { computed, onMounted, ref } from "vue"
import components from "@/data/components"
import { getComponentRoot } from "@/utils/helpers"

const props = defineProps({
	block: {
		type: Block,
		required: true,
	},
})

const componentRef = ref(null)
const styles = computed(() => props.block.getStyles())

const componentProps = computed(() => {
	return {
		...props.block.componentProps,
	}
})

onMounted(() => {
	// set data-component-id on mount since some frappeui components have inheritAttrs: false
	const componentRoot = getComponentRoot(componentRef)
	if (componentRoot) {
		componentRoot.setAttribute("data-component-id", props.block.componentId)
	}
})
</script>
