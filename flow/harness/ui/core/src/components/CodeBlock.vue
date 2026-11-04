<template>
	<div
		class="flow-code overflow-hidden"
		:class="bare ? '' : 'rounded-6 border border-outline-gray-2 bg-surface-gray-1'"
	>
		<div
			class="flex items-center justify-between gap-2 border-b border-outline-gray-1 py-1 pl-3 pr-1"
			:class="bare ? '' : 'bg-surface-gray-2'"
		>
			<span class="min-w-0 truncate font-mono text-xs text-ink-gray-5">{{ lang ?? "text" }}</span>
			<CopyButton :text="code" title="Copy code" />
		</div>
		<pre><code v-html="html" /></pre>
	</div>
</template>

<script setup>
import { computed } from "vue"

import { highlightCode } from "../markdown.js"
import CopyButton from "./CopyButton.vue"

const props = defineProps({
	code: { type: String, required: true },
	lang: { type: String, default: null },
	// a host panel that frames the block itself: drop the border, radius and fill
	bare: { type: Boolean, default: false },
})

const html = computed(() => highlightCode(props.code, props.lang))
</script>
