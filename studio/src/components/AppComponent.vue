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
import { computed, onMounted, ref, useAttrs } from "vue"
import components from "@/data/components"
import { getComponentRoot, isDynamicValue, getDynamicValue } from "@/utils/helpers"

import useAppStore from "@/stores/appStore"

const props = defineProps({
	block: {
		type: Block,
		required: true,
	},
})

const componentRef = ref(null)
const styles = computed(() => props.block.getStyles())

const store = useAppStore()
const getComponentProps = () => {
	if (!props.block || props.block.isRoot()) return []

	const componentProps = { ...props.block.componentProps }

	Object.entries(componentProps).forEach(([propName, config]) => {
		if (isDynamicValue(config)) {
			// get dynamic value for "{{ a.b.c }}" from "store.resources?.a?.b?.c"
			const pathToProperty = config.slice(2, -2).trim()
			componentProps[propName] = getDynamicValue(store.resources, pathToProperty)
		}
	})
	return componentProps
}

const attrs = useAttrs()
const componentProps = computed(() => {
	return {
		...getComponentProps(),
		...attrs,
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
