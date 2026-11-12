<!-- Rendered markdown: prose chunks stay sanitized v-html, top-level code
     blocks become CodeBlock components, top-level tables get their own scroll
     box. A list or quote holding code renders each item through this component.
     Spacing lives on .flow-md-seg, a table's on .flow-md-table. -->
<template>
	<div class="flow-md">
		<template v-for="(seg, i) in parts" :key="i">
			<CodeBlock v-if="seg.type === 'code'" class="flow-md-seg" :code="seg.code" :lang="seg.lang" />
			<!-- the scroll box outlives each streamed re-render, so it keeps its scroll -->
			<div v-else-if="seg.type === 'table'" class="flow-md-table" v-html="seg.html" />
			<ol v-else-if="seg.type === 'list' && seg.ordered" :start="seg.start">
				<li v-for="(item, j) in seg.items" :key="j"><MarkdownContent :segments="item" /></li>
			</ol>
			<ul v-else-if="seg.type === 'list'">
				<li v-for="(item, j) in seg.items" :key="j"><MarkdownContent :segments="item" /></li>
			</ul>
			<blockquote v-else-if="seg.type === 'quote'"><MarkdownContent :segments="seg.segments" /></blockquote>
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
	// already split, for a list item or quote
	segments: { type: Array, default: null },
})

const parts = computed(() => props.segments ?? renderMarkdownSegments(props.text))
</script>
