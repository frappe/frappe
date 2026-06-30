<script setup>
import { computed } from "vue";
import { argEntries } from "@/lib/toolMeta";

// Tool-call inputs as a spec: scalars in two columns, nested values in a block.
const props = defineProps({ arguments: { default: null } });

const entries = computed(() => argEntries(props.arguments));
</script>

<template>
	<dl
		v-if="entries.length"
		class="grid grid-cols-[max-content_1fr] items-baseline gap-x-4 gap-y-1.5"
	>
		<template v-for="e in entries" :key="e.key">
			<template v-if="e.kind === 'inline'">
				<dt class="text-xs text-ink-gray-5">{{ e.label }}</dt>
				<dd class="min-w-0 break-words text-sm text-ink-gray-8">{{ e.value }}</dd>
			</template>
			<div v-else class="col-span-2 min-w-0">
				<div class="mb-1 text-xs text-ink-gray-5">{{ e.label }}</div>
				<pre class="flow-arg-block">{{ e.value }}</pre>
			</div>
		</template>
	</dl>
</template>

<style scoped>
.flow-arg-block {
	margin: 0;
	max-height: 240px;
	overflow: auto;
	white-space: pre-wrap;
	word-break: break-word;
	border-radius: 6px;
	background: var(--surface-gray-2);
	padding: 8px 10px;
	font-family: var(--font-stack-monospace, ui-monospace, monospace);
	font-size: 11.5px;
	line-height: 1.6;
	color: var(--ink-gray-8);
}
</style>
