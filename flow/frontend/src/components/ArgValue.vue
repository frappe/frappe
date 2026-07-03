<script setup>
import { computed } from "vue";
import { FeatherIcon } from "@/lib/ui";
import CodeBlock from "./CodeBlock.vue";
import ChipList from "./ChipList.vue";
import ClampText from "./ClampText.vue";
import ConditionChip from "./ConditionChip.vue";
import RecordsList from "./RecordsList.vue";
import { humanize, argKind, formatScalar, isConditionObject, isLongText } from "@/lib/toolMeta";

// Renders an args object: compact values as one wrapping chip row, block values
// (long text, lists, filters, records, code) as labeled sections below it.
// `blockKeys` forces given keys to the "text" block form so a field renders the
// same way across sibling records (passed by RecordsList).
const props = defineProps({
	value: { type: Object, required: true },
	blockKeys: { type: Object, default: () => new Set() },
});

const kindFor = (k, v) => {
	// A `code` key or any multi-line string is code, whatever its length.
	const base = k === "code" && typeof v === "string" && v ? "code" : argKind(v);
	if (base === "code") return "code";
	if (typeof v === "string" && v && (props.blockKeys.has(k) || isLongText(v))) return "text";
	return base;
};
const INLINE = new Set(["scalar", "empty", "tuple"]);

const entries = computed(() => Object.entries(props.value));
const chips = computed(() => entries.value.filter(([k, v]) => INLINE.has(kindFor(k, v))));
const sections = computed(() =>
	entries.value
		.filter(([k, v]) => !INLINE.has(kindFor(k, v)))
		.map(([k, v]) => ({ key: k, value: v, kind: kindFor(k, v) }))
);
</script>

<template>
	<div class="flex flex-col gap-3">
		<div v-if="chips.length" class="flex flex-col items-start gap-1.5">
			<template v-for="[k, v] in chips" :key="k">
				<ConditionChip v-if="argKind(v) === 'tuple'" :field="humanize(k)" :value="v" />
				<span
					v-else-if="typeof v === 'boolean'"
					class="inline-flex items-center gap-1 rounded-lg border border-outline-gray-1 py-1 pl-2 pr-2.5"
				>
					<FeatherIcon
						:name="v ? 'check' : 'minus'"
						class="h-3 w-3 shrink-0"
						:class="v ? 'text-ink-green-3' : 'text-ink-gray-4'"
					/>
					<span class="text-xs text-ink-gray-7">{{ humanize(k) }}</span>
				</span>
				<span
					v-else
					class="inline-flex items-baseline gap-2 rounded-lg border border-outline-gray-1 py-1 pl-2.5 pr-3"
				>
					<span class="text-xs text-ink-gray-5">{{ humanize(k) }}</span>
					<span class="break-words text-[13px] font-medium text-ink-gray-9">
						{{ formatScalar(v) }}
					</span>
				</span>
			</template>
		</div>

		<div v-for="s in sections" :key="s.key">
			<div class="mb-1.5 text-[11px] font-semibold uppercase tracking-wide text-ink-gray-4">
				{{ humanize(s.key) }}
			</div>

			<CodeBlock v-if="s.kind === 'code'" :code="String(s.value)" />

			<ClampText v-else-if="s.kind === 'text'" :text="String(s.value)" />

			<ChipList v-else-if="s.kind === 'list'" :items="s.value" />

			<RecordsList v-else-if="s.kind === 'records'" :records="s.value" />

			<div v-else-if="isConditionObject(s.value)" class="flex flex-col items-start gap-1.5">
				<ConditionChip
					v-for="[field, v] in Object.entries(s.value)"
					:key="field"
					:field="field"
					:value="v"
				/>
			</div>

			<div v-else class="pl-3">
				<ArgValue :value="s.value" />
			</div>
		</div>
	</div>
</template>
