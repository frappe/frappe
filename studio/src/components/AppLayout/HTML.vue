<template>
	<div class="!relative" ref="component" v-html="_html"></div>
</template>

<script setup lang="ts">
import { ref, computed } from "vue"
import type { HTMLProps } from "@/types/studio_components/HTML"
import { isEditor } from "@/utils/helpers"

const component = ref<HTMLElement | null>(null)
const props = defineProps<HTMLProps>()

const _html = computed(() => {
	if (isEditor()) {
		return `
			<div class="absolute top-0 bottom-0 right-0 left-0"></div>
			${props.html}
		`
	}
	return props.html
})

defineExpose({
	component,
})
</script>
