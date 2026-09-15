<template>
	<div class="child-table child-table--plain child-table--bordered pfb-summary-preview">
		<table class="table">
			<thead>
				<tr>
					<th
						v-for="(cell, i) in head1"
						:key="'h1' + i"
						:colspan="cell.colspan"
						:rowspan="cell.rowspan"
					>
						{{ cell.label }}
					</th>
				</tr>
				<tr v-if="head2.length">
					<th v-for="(cell, i) in head2" :key="'h2' + i">{{ cell.label }}</th>
				</tr>
			</thead>
			<tbody>
				<tr>
					<td class="text-muted pfb-summary-note" :colspan="leaf_count">
						{{
							df.source
								? __("Groups of {0} by {1} — computed on print", [
										df.source,
										df.group_by || "?",
								  ])
								: __("Pick a source table in the panel")
						}}
					</td>
				</tr>
			</tbody>
		</table>
	</div>
</template>

<script setup>
import { computed } from "vue";

const props = defineProps(["df"]);

let leaf_count = computed(() => (props.df.columns || []).length || 1);

// Mirrors the header-group builder in PrintFormatGenerator.prepare_summary_table —
// the canvas renders headers before any doc exists, so it can't ask the server
let heads = computed(() => {
	const columns = props.df.columns || [];
	const head1 = [];
	const head2 = [];
	let i = 0;
	while (i < columns.length) {
		const group = columns[i].group;
		if (!group) {
			head1.push({ label: columns[i].label || "", colspan: 1, rowspan: 2 });
			i += 1;
			continue;
		}
		let span = 0;
		while (i + span < columns.length && columns[i + span].group === group) {
			head2.push({ label: columns[i + span].label || "" });
			span += 1;
		}
		head1.push({ label: group, colspan: span, rowspan: 1 });
		i += span;
	}
	if (!head2.length) {
		return { head1: head1.map((c) => ({ ...c, rowspan: 1 })), head2 };
	}
	return { head1, head2 };
});
let head1 = computed(() =>
	heads.value.head1.length
		? heads.value.head1
		: [{ label: __("Summary"), colspan: 1, rowspan: 1 }]
);
let head2 = computed(() => heads.value.head2);
</script>

<style scoped>
.pfb-summary-preview .table {
	width: 100%;
}
.pfb-summary-note {
	text-align: center;
	font-size: var(--text-xs);
	padding: 6px;
}
</style>
