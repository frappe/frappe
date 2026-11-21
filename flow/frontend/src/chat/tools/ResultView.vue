<template>
	<div v-if="cut" class="px-3 py-2.5 text-sm text-ink-gray-5">{{ __("Too large to show here") }}</div>
	<div v-else-if="blank(value)" class="px-3 py-2.5 text-sm text-ink-gray-5">{{ __("No result") }}</div>
	<DataView v-else-if="isTable(value)" :value="value" />
	<div v-else class="flex items-start gap-2 px-3 py-2.5">
		<div class="max-h-[260px] min-w-0 flex-1 overflow-auto text-sm leading-relaxed text-ink-gray-7">
			<DataView :value="value" />
		</div>
		<CopyButton v-if="typeof value === 'string'" :text="value" />
	</div>
</template>

<script setup>
import { computed } from "vue";
import CopyButton from "@flow/ui-core/components/CopyButton.vue";
import { __ } from "@flow/ui-core/translate.js";

import DataView from "./DataView.vue";
import { blank, isTable } from "./result.js";

// A return no other view draws: a custom Imported or Script tool's, a function's, code's.
const props = defineProps({
	arguments: { type: Object, default: () => ({}) },
	result: { type: Object, default: null },
	// the part of the return to draw, where a tool wraps its own
	part: { type: String, default: "" },
});

// a tool that returns text sends it as it is; anything else arrives as JSON
const value = computed(() => {
	const content = props.result?.content ?? "";
	try {
		const parsed = JSON.parse(content);
		return props.part ? parsed?.[props.part] : parsed;
	} catch {
		return content;
	}
});

// cut JSON no longer parses, and its text is half a record and a note to the model. JSON
// arrives as one line, so the cut's note follows it at once; cut text keeps its lines.
const cut = computed(
	() =>
		!!props.result?.details?.truncation?.truncated &&
		typeof value.value === "string" &&
		/^\s*[[{].*\n\n\[Cut /.test(value.value)
);
</script>
