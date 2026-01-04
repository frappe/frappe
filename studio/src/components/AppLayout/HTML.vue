<template>
	<component ref="component" v-if="compiledTemplate" :is="compiledTemplate"></component>
	<div ref="component" v-else v-html="props.html"></div>
</template>
<script setup lang="ts">
import { computed, ref, compile } from "vue"
import type { HTMLProps } from "@/types/studio_components/HTML"

const component = ref<HTMLElement | null>(null)
const props = defineProps<HTMLProps>()

const compiledTemplate = computed(() => {
	if (!props.html) return null
	try {
		return compile(props.html)
	} catch (e) {
		console.log("Error compiling template:", e)
		return null
	}
})

defineExpose({
	component,
})
</script>
