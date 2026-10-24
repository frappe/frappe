<template>
	<div class="flex items-start gap-2 px-3 py-2.5">
		<pre
			class="m-0 max-h-[240px] min-w-0 flex-1 overflow-auto whitespace-pre-wrap break-words font-mono text-xs leading-[1.65] text-ink-gray-6"
			>{{ output }}</pre
		>
		<CopyButton
			:text="output"
			class="grid h-5 w-5 flex-none place-items-center rounded-4 text-ink-gray-5 hover:bg-surface-gray-2 hover:text-ink-gray-8"
		/>
	</div>
</template>

<script setup>
import { computed } from "vue";
import CopyButton from "@flow/ui-core/components/CopyButton.vue";

import { pretty } from "./result.js";

// Every other tool: a custom Imported or Script tool, whose return is whatever it is.
const props = defineProps({
	arguments: { type: Object, required: true },
	result: { type: Object, default: null },
});

const output = computed(() => pretty(props.result?.content));
</script>
