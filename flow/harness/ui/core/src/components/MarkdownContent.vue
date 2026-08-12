<!-- Rendered markdown: prose chunks stay sanitized v-html, top-level code
     blocks become CodeBlock components. Segment spacing lives on .flow-md-seg. -->
<template>
	<div class="flow-md">
		<template v-for="(seg, i) in segments" :key="i">
			<CodeBlock v-if="seg.type === 'code'" class="flow-md-seg" :code="seg.code" :lang="seg.lang" />
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
