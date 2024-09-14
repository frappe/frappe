<template>
	<component
		:is="components.getComponent(block.componentName) || block.componentName"
		v-bind="componentProps"
		:data-component-id="block.componentId"
		:style="styles"
	>
		<AppComponent v-for="child in block?.children" :key="child.componentId" :block="child" />
	</component>
</template>

<script setup>
import Block from "@/utils/block"
import { computed } from "vue"
import components from "@/data/components"

const props = defineProps({
	block: {
		type: Block,
		required: true,
	},
})

const styles = computed(() => props.block.getStyles())

const componentProps = computed(() => {
	return {
		...props.block.componentProps,
	}
})
</script>
