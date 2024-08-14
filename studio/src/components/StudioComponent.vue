<template>
	<component :is="componentName" v-bind="componentData.initialState"> </component>
</template>

<script setup>
import { computed } from "vue"
import components from "@/data/components"

const props = defineProps({
	componentName: {
		type: String,
		required: true,
	},
})

const componentData = computed(() => components.get(props.componentName))
</script>
