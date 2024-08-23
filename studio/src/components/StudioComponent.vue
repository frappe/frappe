<template>
	<component
		:is="block.componentName"
		v-bind="componentData.initialState"
		:data-component-id="block.componentId"
		:style="styles"
	>
		<StudioComponent v-for="child in block.children" :key="child.componentId" :block="child" />
	</component>
</template>

<script setup>
import { computed } from "vue"
import components from "@/data/components"
import Block from "@/utils/block"

const props = defineProps({
	block: {
		type: Block,
		required: true,
	},
})

const componentData = computed(() => {
	if (props.block.componentName === "div") return { initialState: {} }
	return components.get(props.block.componentName)
})

const styles = computed(() => {
	return props.block.getStyles()
})
</script>
