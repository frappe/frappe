<template>
	<div>
		<div v-if="values.length" class="border-b border-outline-gray-1 px-3 py-2.5">
			<table class="border-collapse text-left text-xs">
				<tbody class="text-ink-gray-7">
					<tr v-for="[field, value] in values" :key="field" class="align-top">
						<td class="whitespace-nowrap py-0.5 pr-3 text-ink-gray-5">
							{{ humanize(field) }}
						</td>
						<td class="max-w-[320px] truncate py-0.5">
							<ValueView :value="value" />
						</td>
					</tr>
				</tbody>
			</table>
		</div>
		<RecordTable
			:columns="columns"
			:rows="rows"
			:doctype="doctype"
			:link-column="linked ? 'name' : ''"
			status-label="error"
		/>
	</div>
</template>

<script setup>
import { computed } from "vue";

import RecordTable from "./RecordTable.vue";
import ValueView from "./ValueView.vue";
import { columnsOf, humanize, parseResult } from "./result.js";

// The record-name tools: update, delete and run_action. What each did comes from the
// result's own shape, so the view needs no tool name.
const props = defineProps({
	arguments: { type: Object, required: true },
	result: { type: Object, default: null },
});

const parsed = computed(() => parseResult(props.result));
const doctype = computed(() => props.arguments.doctype ?? "");
const values = computed(() =>
	Object.entries(props.arguments.values ?? props.arguments.args ?? {})
);
// deleted records have no form left to open
const linked = computed(() => !!doctype.value && !parsed.value?.deleted);

const rows = computed(() => {
	const result = parsed.value;
	const names = props.arguments.names ?? [];
	if (result?.action === "rename")
		return [{ cells: { name: result.old, renamed_to: result.new } }];
	if (!result) return names.map((name) => ({ cells: { name } }));

	const errors = new Map(
		(result.failures ?? []).map((failure) => [failure.name, failure.error])
	);
	const outcomes = new Map((result.results ?? []).map((row) => [row.name, row.result]));
	const done = new Set(result.updated ?? result.deleted ?? [...outcomes.keys()]);
	return names.map((name) => {
		if (errors.has(name)) return { cells: { name }, status: { error: errors.get(name) } };
		if (!done.has(name)) return { cells: { name } };
		const outcome = outcomes.get(name);
		return { cells: { name, ...amended(outcome, name), ...returned(outcome) } };
	});
});
const columns = computed(() => columnsOf(rows.value.map((row) => row.cells)));

// amend answers with the record it created; a whitelisted method with whatever it returns
function amended(outcome, name) {
	return outcome?.name && outcome.name !== name ? { renamed_to: outcome.name } : {};
}

function returned(outcome) {
	return outcome == null ? {} : { returned: outcome };
}
</script>
