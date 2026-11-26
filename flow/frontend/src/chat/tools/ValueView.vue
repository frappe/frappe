<template>
	<details v-if="folds" @toggle="open = $event.target.open">
		<summary class="cursor-pointer text-ink-gray-6">
			{{ Array.isArray(value) ? cellText(value) : __("Details") }}
		</summary>
		<template v-if="open">
			<pre
				v-if="json"
				class="m-0 mt-1 max-h-[200px] overflow-auto whitespace-pre-wrap break-words font-mono text-sm"
				>{{ JSON.stringify(value, null, 2) }}</pre
			>
			<div v-else class="mt-1 max-h-[200px] overflow-auto whitespace-normal">
				<table class="border-collapse text-left">
					<tbody>
						<tr v-for="[field, part] in Object.entries(value)" :key="field" class="align-top">
							<td v-if="!Array.isArray(value)" class="whitespace-nowrap pr-3 text-ink-gray-5">
								{{ humanize(field) }}
							</td>
							<td class="whitespace-pre-wrap break-words">{{ cellText(part, true) }}</td>
						</tr>
					</tbody>
				</table>
			</div>
		</template>
	</details>
	<span v-else :title="cellText(value)">{{ cellText(value) }}</span>
</template>

<script setup>
import { computed, ref } from "vue";
import { __ } from "@flow/ui-core/translate.js";

import { blank, cellText, humanize } from "./result.js";

// A cell's value. A structured one folds, and opens to a line per field or item: a
// table's cell has no room for more, so what lies deeper reads on its line.
const props = defineProps({
	value: { default: null },
	// a DocType field's value: a structured one is a JSON field, so it opens as JSON
	json: { type: Boolean, default: false },
});
const open = ref(false);
const structured = computed(() => props.value !== null && typeof props.value === "object");
// a list of plain values already reads whole on its line
const listed = computed(
	() => Array.isArray(props.value) && props.value.every((item) => item === null || typeof item !== "object")
);
// an empty list or record has nothing to open; a JSON field's empty record still shows as {}
const folds = computed(() => {
	if (!structured.value) return false;
	if (props.json) return !Array.isArray(props.value) || props.value.length > 0;
	return !listed.value && !blank(props.value);
});
</script>
