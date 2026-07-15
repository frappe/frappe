<script setup>
import { ref, computed } from "vue";
import { __ } from "@/lib/translate";

// Code with a line-preview toggle.
const props = defineProps({ code: { type: String, default: "" } });

const PREVIEW_LINES = 4;

const lines = computed(() => props.code.split("\n"));
const hasMore = computed(() => lines.value.length > PREVIEW_LINES);
const expanded = ref(false);
const shown = computed(() =>
	hasMore.value && !expanded.value ? lines.value.slice(0, PREVIEW_LINES).join("\n") : props.code
);
</script>

<template>
	<div>
		<pre class="arg-code">{{ shown }}</pre>
		<button
			v-if="hasMore"
			class="mt-1 text-xs text-ink-gray-5 hover:text-ink-gray-7"
			@click="expanded = !expanded"
		>
			{{
				expanded
					? __("Show less")
					: __("Show {0} more lines", [lines.length - PREVIEW_LINES])
			}}
		</button>
	</div>
</template>

<style scoped>
.arg-code {
	margin: 0;
	max-height: 320px;
	overflow: auto;
	white-space: pre-wrap;
	word-break: break-word;
	border-radius: 8px;
	background: var(--surface-gray-2);
	padding: 8px 10px;
	font-family: var(--font-stack-monospace, ui-monospace, monospace);
	font-size: 12.5px;
	line-height: 1.6;
	color: var(--ink-gray-8);
}
</style>
