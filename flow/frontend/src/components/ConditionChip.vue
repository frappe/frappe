<script setup>
import { computed } from "vue";
import { argKind, formatScalar } from "@/lib/toolMeta";

// One condition as field → operator badge → value chips. Value may be a filter
// tuple (its own operator), a scalar list ("in"), or a scalar ("=").
const props = defineProps({
	field: { type: String, required: true },
	value: { default: null },
});

const parts = computed(() => {
	const v = props.value;
	const kind = argKind(v);
	if (kind === "tuple") return { op: v[0], values: Array.isArray(v[1]) ? v[1] : [v[1]] };
	if (kind === "list") return { op: "in", values: v };
	return { op: "=", values: [v] };
});
</script>

<template>
	<span
		class="inline-flex flex-wrap items-center gap-1.5 rounded-lg border border-outline-gray-1 bg-surface-gray-1 px-2.5 py-1"
	>
		<span class="text-[13px] font-medium text-ink-gray-9">{{ field }}</span>
		<span
			class="rounded-full bg-surface-gray-2 px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wider text-ink-gray-6"
		>
			{{ parts.op }}
		</span>
		<span
			v-for="(item, i) in parts.values"
			:key="i"
			class="rounded border border-outline-gray-2 bg-surface-white px-1.5 py-0.5 text-xs text-ink-gray-8"
		>
			{{ formatScalar(item) }}
		</span>
	</span>
</template>
