<template>
	<MarkdownContent :text="block.text" class="flow-prose text-ink-gray-8" />
</template>

<script setup>
import MarkdownContent from "./MarkdownContent.vue"

defineProps({
	block: { type: Object, required: true },
})
</script>
