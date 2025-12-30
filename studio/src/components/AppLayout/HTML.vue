<template>
	<div ref="component" class="!relative" v-html="HTML"></div>
</template>
<script setup lang="ts">
import { computed, ref } from "vue"
import type { HTMLProps } from "@/types/studio_components/HTML"

const component = ref<HTMLElement | null>(null)
const props = defineProps<HTMLProps>()

const HTML = computed(() => {
	let content = props.html
	return `
		<div class="absolute top-0 bottom-0 right-0 left-0"></div>
		${content}
	`
})

defineExpose({
	component,
})
</script>
