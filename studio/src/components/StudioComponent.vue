<template>
	<component :is="componentName" v-bind="componentData.initialState" :data-component-id="componentId">
		<StudioComponent
			v-for="child in children"
			:key="child.componentId"
			:componentName="child.componentName"
			:componentId="child.componentId"
			:children="child.children"
		/>
	</component>
</template>

<script setup>
import { computed } from "vue"
import components from "@/data/components"

const props = defineProps({
	componentName: {
		type: String,
		required: true,
	},
	componentId: {
		type: String,
		required: true,
	},
	children: {
		type: Array,
		default: () => [],
		required: false,
	},
})

const componentData = computed(() => {
	if (props.componentName === "div") return { initialState: {} }
	return components.get(props.componentName)
})
</script>
