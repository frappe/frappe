<!-- Rendered markdown: prose chunks stay sanitized v-html, top-level code
     blocks become CodeBlock components, top-level tables get their own scroll
     box. Spacing lives on .flow-md-seg, a table's on .flow-md-table. -->
<template>
	<div class="flow-md">
		<template v-for="(seg, i) in segments" :key="i">
			<CodeBlock v-if="seg.type === 'code'" class="flow-md-seg" :code="seg.code" :lang="seg.lang" />
			<!-- the scroll box outlives each streamed re-render, so it keeps its scroll -->
			<div v-else-if="seg.type === 'table'" class="flow-md-table" v-html="seg.html" />
			<div v-else class="flow-md-seg" v-html="seg.html" />
		</template>
	</div>
</template>

<script setup>
import { computed } from "vue"

import { renderMarkdownSegments } from "../markdown.js"
import CodeBlock from "./CodeBlock.vue"

const props = defineProps({
	text: { type: String, default: "" },
})

const segments = computed(() => renderMarkdownSegments(props.text))
</script>
