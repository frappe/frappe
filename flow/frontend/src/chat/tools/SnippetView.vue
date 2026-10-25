<template>
	<div v-if="!groups.length" class="px-3 py-2.5 text-xs text-ink-gray-5">No matches</div>
	<div v-else class="flex max-h-[260px] flex-col gap-3 overflow-auto px-3 py-2.5">
		<div v-for="(group, i) in groups" :key="i">
			<div class="mb-1 truncate text-2xs font-medium text-ink-gray-5">{{ group.title }}</div>
			<div
				v-for="(hit, j) in group.hits"
				:key="j"
				class="mt-1 whitespace-pre-wrap break-words border-l-2 border-outline-gray-2 pl-2 text-xs leading-relaxed text-ink-gray-7"
			>
				{{ hit.content }}
			</div>
		</div>
	</div>
</template>

<script setup>
import { computed } from "vue";

import { parseResult } from "./result.js";

// Knowledge chunks and attachment chunks read the same; both arrive sorted by score,
// so same-source hits sit together and share one heading.
const props = defineProps({
	arguments: { type: Object, required: true },
	result: { type: Object, default: null },
});

const groups = computed(() => {
	const hits = parseResult(props.result);
	if (!Array.isArray(hits)) return [];
	const groups = [];
	for (const hit of hits) {
		const title = hit.file ?? hit.source ?? "";
		const last = groups.at(-1);
		if (last?.title === title) last.hits.push(hit);
		else groups.push({ title, hits: [hit] });
	}
	return groups;
});
</script>
