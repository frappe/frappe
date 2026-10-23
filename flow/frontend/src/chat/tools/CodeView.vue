<template>
	<div>
		<CodeBlock :code="code" lang="python" bare />
		<template v-if="output">
			<div class="border-y border-outline-gray-1 px-3 py-1.5 text-2xs text-ink-gray-4">
				Result
			</div>
			<pre
				class="m-0 max-h-[200px] overflow-auto whitespace-pre-wrap break-words px-3 py-2 font-mono text-xs leading-[1.65] text-ink-gray-6"
				>{{ output }}</pre
			>
		</template>
	</div>
</template>

<script setup>
import { computed } from "vue";
import CodeBlock from "@flow/ui-core/components/CodeBlock.vue";

import { pretty } from "./result.js";

const props = defineProps({
	arguments: { type: Object, required: true },
	result: { type: Object, default: null },
});

const code = computed(() => props.arguments.code ?? "");
const output = computed(() => (props.result?.is_error ? "" : pretty(props.result?.content)));
</script>
