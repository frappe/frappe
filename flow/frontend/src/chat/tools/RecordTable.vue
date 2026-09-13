<template>
	<div v-if="!rows.length" class="px-3 py-2.5 text-xs text-ink-gray-5">No records</div>
	<div v-else>
		<div class="max-h-[260px] overflow-auto">
			<table class="w-full border-collapse text-left text-xs">
				<thead>
					<tr>
						<th
							v-if="withStatus"
							class="sticky top-0 whitespace-nowrap bg-surface-gray-1 px-3 py-1.5 font-medium text-ink-gray-5"
						>
							{{ humanize(statusLabel) }}
						</th>
						<th
							v-for="column in columns"
							:key="column"
							class="sticky top-0 whitespace-nowrap bg-surface-gray-1 px-3 py-1.5 font-medium text-ink-gray-5"
						>
							{{ humanize(column) }}
						</th>
					</tr>
				</thead>
				<tbody class="text-ink-gray-7">
					<tr
						v-for="(row, i) in visible"
						:key="i"
						class="border-t border-outline-gray-1"
					>
						<td v-if="withStatus" class="max-w-[240px] truncate px-3 py-1.5 align-top">
							<span
								v-if="row.status?.error"
								class="text-ink-red-6"
								:title="row.status.error"
								>{{ row.status.error }}</span
							>
							<a
								v-else-if="row.status?.name"
								:href="deskUrl(doctype, row.status.name)"
								target="_blank"
								class="text-ink-gray-8 hover:underline"
								>{{ row.status.name }}</a
							>
						</td>
						<td
							v-for="column in columns"
							:key="column"
							class="max-w-[220px] truncate px-3 py-1.5 align-top"
							:title="cellText(row.cells[column])"
						>
							<a
								v-if="column === linkColumn && doctype && row.cells[column]"
								:href="deskUrl(doctype, row.cells[column])"
								target="_blank"
								class="text-ink-gray-8 hover:underline"
								>{{ cellText(row.cells[column]) }}</a
							>
							<ValueView v-else :value="row.cells[column]" />
						</td>
					</tr>
				</tbody>
			</table>
		</div>
		<button
			v-if="hidden"
			type="button"
			class="w-full border-t border-outline-gray-1 px-3 py-1.5 text-left text-2xs text-ink-gray-6 hover:bg-surface-gray-1"
			@click="visibleCount += PAGE_SIZE"
		>
			Show {{ Math.min(hidden, PAGE_SIZE) }} more ({{ hidden }} remaining)
		</button>
	</div>
</template>

<script setup>
import { computed, ref } from "vue";

import ValueView from "./ValueView.vue";
import { cellText, deskUrl, humanize } from "./result.js";

// Rows are { cells, status? }; the leading column appears only where a status has
// something to say — the record a row created, or why it failed — and the view that
// fills it names it. The table fills its
// panel edge to edge, so the panel's own border frames it.
const props = defineProps({
	columns: { type: Array, required: true },
	rows: { type: Array, required: true },
	doctype: { type: String, default: "" },
	linkColumn: { type: String, default: "" },
	statusLabel: { type: String, default: "name" },
});

const PAGE_SIZE = 20;
const visibleCount = ref(PAGE_SIZE);

const withStatus = computed(() => props.rows.some((row) => row.status?.name || row.status?.error));
const visible = computed(() => props.rows.slice(0, visibleCount.value));
const hidden = computed(() => props.rows.length - visible.value.length);
</script>
