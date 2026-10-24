<template>
	<div v-if="!rows.length" class="px-3 py-2.5 text-xs text-ink-gray-5">No records</div>
	<div v-else>
		<div class="overflow-auto" :class="open.size ? '' : 'max-h-[260px]'">
			<table class="w-full border-collapse text-left text-xs">
				<thead>
					<tr>
						<th
							v-if="withStatus"
							class="sticky top-0 whitespace-nowrap bg-surface-gray-1 px-3 py-1.5 font-medium text-ink-gray-5"
						>
							Name
						</th>
						<th
							v-for="column in columns"
							:key="column"
							class="sticky top-0 whitespace-nowrap bg-surface-gray-1 px-3 py-1.5 font-medium text-ink-gray-5"
						>
							{{ labels?.[column] || humanize(column) }}
						</th>
					</tr>
				</thead>
				<tbody class="text-ink-gray-7">
					<template v-for="(row, i) in visible" :key="i">
						<tr class="border-t border-outline-gray-1">
							<td
								v-if="withStatus"
								class="max-w-[240px] truncate px-3 py-1.5 align-top"
							>
								<a
									v-if="row.status?.name"
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
								<button
									v-else-if="isTable(row.cells[column])"
									type="button"
									class="inline-flex items-center gap-1 text-ink-gray-6 hover:text-ink-gray-8"
									:aria-expanded="open.has(key(i, column))"
									@click="toggle(i, column)"
								>
									<FeatherIcon
										name="chevron-right"
										class="h-3 w-3 transition-transform"
										:class="open.has(key(i, column)) ? 'rotate-90' : ''"
									/>
									{{ cellText(row.cells[column]) }}
								</button>
								<ValueView v-else :value="row.cells[column]" />
							</td>
						</tr>
						<tr
							v-for="column in opened(i)"
							:key="column"
							ref="unfolded"
							:data-key="key(i, column)"
							class="border-t border-outline-gray-1"
						>
							<td :colspan="span" class="bg-surface-gray-1 px-3 py-2">
								<div class="mb-1.5 text-2xs font-medium text-ink-gray-5">
									{{ humanize(column) }}
								</div>
								<div
									class="overflow-hidden rounded-[6px] border border-outline-gray-1 bg-surface-base"
								>
									<RecordTable
										:columns="columnsOf(row.cells[column])"
										:rows="row.cells[column].map((cells) => ({ cells }))"
									/>
								</div>
							</td>
						</tr>
					</template>
				</tbody>
				<tfoot v-if="footer">
					<tr>
						<td v-if="withStatus" class="sticky bottom-0 bg-surface-gray-1" />
						<td
							v-for="column in columns"
							:key="column"
							class="sticky bottom-0 max-w-[220px] truncate bg-surface-gray-1 px-3 py-1.5 align-top font-medium text-ink-gray-8"
						>
							<ValueView :value="footer[column]" />
						</td>
					</tr>
				</tfoot>
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
import { computed, nextTick, reactive, ref } from "vue";
import FeatherIcon from "@flow/ui-core/components/FeatherIcon.vue";

import ValueView from "./ValueView.vue";
import { cellText, columnsOf, deskUrl, humanize, isTable } from "./result.js";

// Rows are { cells, status? }; the leading column appears only where a status names
// the record a row created. A child table stays a count in its cell; opened, it unfolds as a
// table of its own in a row beneath, spanning the width, and the cap on the height
// lifts so nothing scrolls inside a scroll. Like a tool's dropdown, a row that unfolds
// past the bottom edge is nudged into view. The table fills its panel edge to edge, so
// the panel's own border frames it. A footer row, like a report's total, stays pinned.
const props = defineProps({
	columns: { type: Array, required: true },
	rows: { type: Array, required: true },
	doctype: { type: String, default: "" },
	linkColumn: { type: String, default: "" },
	footer: { type: Object, default: null },
	labels: { type: Object, default: null },
});

const PAGE_SIZE = 20;
const visibleCount = ref(PAGE_SIZE);
const open = reactive(new Set());
const unfolded = ref([]);

const withStatus = computed(() => props.rows.some((row) => row.status?.name));
const span = computed(() => props.columns.length + (withStatus.value ? 1 : 0));
const visible = computed(() => props.rows.slice(0, visibleCount.value));
const hidden = computed(() => props.rows.length - visible.value.length);

const key = (i, column) => `${i}:${column}`;
const opened = (i) => props.columns.filter((column) => open.has(key(i, column)));
async function toggle(i, column) {
	const k = key(i, column);
	if (open.has(k)) return open.delete(k);
	open.add(k);
	await nextTick();
	unfolded.value
		.find((el) => el.dataset.key === k)
		?.scrollIntoView({ block: "nearest", behavior: "smooth" });
}
</script>
