<template>
	<div class="flow-md flow-prose text-ink-gray-8" v-html="html" />
</template>

<script setup>
import { computed } from "vue"

import { renderMarkdown } from "../markdown.js"

const props = defineProps({
	block: { type: Object, required: true },
})

const html = computed(() => renderMarkdown(props.block.text))
</script>
