<script setup>
import { computed } from "vue";
import CodeBlock from "./CodeBlock.vue";
import ChipList from "./ChipList.vue";
import RecordsList from "./RecordsList.vue";
import { humanize, argKind, formatScalar } from "@/lib/toolMeta";

// Fields render in one bordered table: single values as two-column rows, block
// text (code, long, or multi-line) as full-width rows (label on top, code block
// below) so they keep their place in the field order. Collections (lists, records,
// nested objects) render as full-width sections beneath. `blockKeys` forces a key
// to the block form so a field looks the same across sibling records.
const props = defineProps({
	value: { type: Object, required: true },
	blockKeys: { type: Object, default: () => new Set() },
});

const kindFor = (k, v) => {
	if (typeof v === "string" && v && props.blockKeys.has(k)) return "code";
	return argKind(v);
};

// In the table: two-column single values + full-span block text. Below: collections.
const TABLE = new Set(["scalar", "empty", "tuple", "code"]);
const isFull = (kind) => kind === "code";

const entries = computed(() =>
	Object.entries(props.value).map(([key, value]) => ({ key, value, kind: kindFor(key, value) }))
);
const tableRows = computed(() => entries.value.filter((e) => TABLE.has(e.kind)));
const blocks = computed(() => entries.value.filter((e) => !TABLE.has(e.kind)));

const tupleValues = (v) => (Array.isArray(v[1]) ? v[1] : [v[1]]).map(formatScalar).join(", ");
</script>

<template>
	<div class="flex flex-col gap-4">
		<div
			v-if="tableRows.length"
			class="grid w-fit max-w-full self-start grid-cols-[max-content_1fr] overflow-hidden rounded-lg border border-outline-gray-1 text-sm"
		>
			<template v-for="(row, i) in tableRows" :key="row.key">
				<div
					v-if="isFull(row.kind)"
					class="col-span-2 min-w-0 px-3 py-2"
					:class="{ 'border-t border-outline-gray-1': i }"
				>
					<div
						class="mb-2 pb-0 text-[11px] font-semibold uppercase leading-none tracking-wide text-ink-gray-4"
					>
						{{ humanize(row.key) }}
					</div>
					<CodeBlock :code="String(row.value)" />
				</div>
				<template v-else>
					<div
						class="border-r border-outline-gray-1 px-3 py-1.5 text-ink-gray-5"
						:class="{ 'border-t': i }"
					>
						{{ humanize(row.key) }}
					</div>
					<div
						class="min-w-0 break-words px-3 py-1.5 text-ink-gray-9"
						:class="{ 'border-t border-outline-gray-1': i }"
					>
						<template v-if="row.kind === 'tuple'">
							<span class="text-ink-gray-4">{{ row.value[0] }}</span>
							{{ tupleValues(row.value) }}
						</template>
						<template v-else-if="row.kind === 'empty'">—</template>
						<template v-else>{{ formatScalar(row.value) }}</template>
					</div>
				</template>
			</template>
		</div>

		<div v-for="s in blocks" :key="s.key">
			<div
				class="mb-2 pb-0 text-[11px] font-semibold uppercase leading-none tracking-wide text-ink-gray-4"
			>
				{{ humanize(s.key) }}
			</div>
			<ChipList v-if="s.kind === 'list'" :items="s.value" />
			<RecordsList v-else-if="s.kind === 'records'" :records="s.value" />
			<ArgValue v-else :value="s.value" />
		</div>
	</div>
</template>
