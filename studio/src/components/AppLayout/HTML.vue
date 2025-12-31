<template>
	<component :is="HTML"></component>
</template>
<script setup lang="ts">
import { computed, ref, compile } from "vue"
import type { HTMLProps } from "@/types/studio_components/HTML"

const component = ref<HTMLElement | null>(null)
const props = defineProps<HTMLProps>()

const HTML = computed(() => compile(props.html))

defineExpose({
	component,
})
</script>
