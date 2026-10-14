<!--
  GroupByTable — one row per group: the grouped fields, then one right-aligned column
  per aggregate. It fetches and stores nothing; the host runs the `serializeGroupBy`
  query and passes the rows in. Rows match the List module's height and dividers, so
  a grouped list reads like the list it summarizes.

  The `#cell` slot gets `{ row, column, value }` so a host can draw what the library
  can't know, like user avatars or a currency symbol. Rows are not clickable:
  a group has no record to open, as in desk's report view. Headers sort and columns
  resize like the List module's; either emits `update:groupBy` with the new `sort` or
  `widths`. With `showTotals`, a last row shows the host's `totals`,
  through the same `#cell` slot with `total: true`.
-->
<template>
	<ScrollArea orientation="both" class="min-h-0 flex-1">
		<FrappeList
			divider="full"
			:columns="tracks"
			:rowHeight="rowHeight"
			class="flex w-max min-w-full flex-col [--list-row-padding-x:theme(spacing.2)]"
		>
			<ListHeader class="group sticky top-0 z-10 bg-surface-base">
				<div
					v-for="column in columns"
					:key="column.key"
					class="relative flex min-w-0"
					:class="column.align === 'right' ? 'justify-end' : ''"
				>
					<ListHeaderCellSort
						class="min-w-0"
						:direction="directionFor(sort, column.id)"
						:align="column.align === 'right' ? 'end' : 'start'"
						@click="update({ sort: nextSort(sort, column.id) })"
					>
						{{ column.label }}
					</ListHeaderCellSort>
					<!-- The same drag handle as the List module: drag to resize, double-click to reset. -->
					<span
						class="absolute inset-y-0 -right-2 flex w-2 cursor-col-resize items-center justify-center"
						@pointerdown.stop.prevent="startResize(handleColumn(column), $event)"
						@dblclick.stop.prevent="resetColumn(handleColumn(column))"
					>
						<span
							class="h-4 border-l border-outline-gray-2 opacity-0 transition-opacity group-hover:opacity-100"
							:class="{ 'opacity-100': resizingFieldname === column.id }"
						/>
					</span>
				</div>
			</ListHeader>
			<template v-if="rows.length">
				<ListRow v-for="(row, i) in rows" :key="i">
					<ListCell
						v-for="column in columns"
						:key="column.key"
						:class="column.align === 'right' ? 'justify-end' : ''"
					>
						<slot
							name="cell"
							:row="row"
							:column="column"
							:value="cellText(row, column)"
						>
							<div
								class="truncate text-base text-ink-gray-8"
								:class="column.align === 'right' ? 'tabular-nums' : ''"
							>
								{{ cellText(row, column) }}
							</div>
						</slot>
					</ListCell>
				</ListRow>
				<ListRow v-if="groupBy.showTotals && totals" data-totals class="font-medium">
					<ListCell
						v-for="(column, i) in columns"
						:key="column.key"
						:class="column.align === 'right' ? 'justify-end' : ''"
					>
						<slot
							name="cell"
							:row="totals"
							:column="column"
							:value="totalText(column, i)"
							:total="true"
						>
							<div
								class="truncate text-base text-ink-gray-9"
								:class="column.align === 'right' ? 'tabular-nums' : ''"
							>
								{{ totalText(column, i) }}
							</div>
						</slot>
					</ListCell>
				</ListRow>
			</template>
			<template v-else-if="loading">
				<ListRow v-for="index in 8" :key="index">
					<ListCell v-for="column in columns" :key="column.key">
						<Skeleton class="h-3 w-full rounded-1" />
					</ListCell>
				</ListRow>
			</template>
			<slot v-else name="empty">
				<div class="flex flex-col items-center gap-1 py-16 text-center">
					<span class="text-base font-medium text-ink-gray-7">{{
						__("No records")
					}}</span>
				</div>
			</slot>
		</FrappeList>
	</ScrollArea>
</template>

<script setup lang="ts">
import { ScrollArea, Skeleton } from "frappe-ui";
import {
	List as FrappeList,
	ListCell,
	ListHeader,
	ListHeaderCellSort,
	ListRow,
} from "frappe-ui/list";
import { computed } from "vue";
import { useDoctypeMeta } from "../../composables/useDoctypeMeta";
import { translate as __ } from "./translate";
import {
	AGGREGATE_FUNCTIONS,
	aggregateKey,
	columnId,
	findGroupByField,
	isCompleteAggregate,
} from "./groupBy";
import { directionFor, nextSort } from "../../experimental/List/headerSort";
import { useColumnResize } from "../../experimental/List/useColumnResize";
import type { Sort } from "../SortBy/types";
import type { GroupByColumn, GroupBySettings, GroupByTableProps } from "./types";

const props = withDefaults(defineProps<GroupByTableProps>(), {
	totals: null,
	loading: false,
	rowHeight: 40,
});

const emit = defineEmits<{ "update:groupBy": [groupBy: GroupBySettings] }>();

const { meta } = useDoctypeMeta(() => props.doctype);

const metaFields = computed(() => meta.value?.fields ?? []);

const columns = computed<GroupByColumn[]>(() => [
	...props.groupBy.fields.map((fieldname) => {
		const field = findGroupByField(metaFields.value, fieldname);
		return {
			key: fieldname,
			id: columnId(fieldname),
			label: __(field?.label ?? fieldname),
			align: "left" as const,
			fieldtype: field?.fieldtype,
			options: field?.options,
		};
	}),
	...props.groupBy.aggregates.filter(isCompleteAggregate).map((a, i) => {
		const fn = AGGREGATE_FUNCTIONS.find((f) => f.value === a.function)?.label ?? "";
		const field = a.fieldname ? findGroupByField(metaFields.value, a.fieldname) : undefined;
		return {
			key: aggregateKey(i),
			id: columnId(a),
			label:
				a.function === "count"
					? __("Count")
					: __("{0} of {1}", [__(fn), __(field?.label ?? a.fieldname ?? "")]),
			align: "right" as const,
			fieldtype: a.function === "count" ? "Int" : field?.fieldtype,
			options: field?.options,
		};
	}),
]);

// Group columns size to their values within a range; aggregates stay narrow so each
// number sits next to its label, wide enough for their header, and a last flexible
// track takes the leftover width. Tracks must be fixed: rows don't share a grid.
// A dragged width (the live draft, then the saved one) beats the automatic size.
const tracks = computed(() => [
	...columns.value.map(
		(c) =>
			drafts[c.id] ??
			props.groupBy.widths?.[c.id] ??
			(c.align === "left" ? "minmax(10rem, 18rem)" : aggregateTrack(c))
	),
	"minmax(0, 1fr)",
]);

const { drafts, resizingFieldname, startResize, resetColumn } = useColumnResize({
	onResize: (key, width) => setWidth(key, width),
	onReset: (key) => setWidth(key, undefined),
});

// useColumnResize speaks in fieldnames; a column's width key stands in for one.
const handleColumn = (column: GroupByColumn) => ({
	fieldname: column.id,
	label: column.label,
});

// The sort the headers show, matching `serializeGroupBy`: the chosen one while its
// column is still shown, else the first aggregate, largest first.
const sort = computed<Sort[]>(() => {
	const chosen = props.groupBy.sort?.[0];
	if (chosen && columns.value.some((c) => c.id === chosen.fieldname)) return [chosen];
	const first = columns.value.find((c) => c.align === "right");
	return first ? [{ fieldname: first.id, direction: "desc" }] : [];
});

function setWidth(key: string, width: string | undefined) {
	const widths = { ...props.groupBy.widths };
	if (width) widths[key] = width;
	else delete widths[key];
	update({ widths: Object.keys(widths).length ? widths : undefined });
}

// Header edits (sort, widths) go back to the host as a whole new grouping.
function update(patch: Partial<GroupBySettings>) {
	const next = { ...props.groupBy, ...patch };
	for (const key of Object.keys(patch) as (keyof GroupBySettings)[]) {
		if (next[key] === undefined) delete next[key];
	}
	emit("update:groupBy", next);
}

// The totals row labels its first column and leaves the other grouped columns blank.
function totalText(column: GroupByColumn, index: number): string {
	if (column.align === "right") return cellText(props.totals ?? {}, column);
	return index === 0 ? __("Total") : "";
}

function aggregateTrack(column: GroupByColumn): string {
	const fit = Math.ceil(column.label.length * 0.5 + 1.5);
	return `${Math.max(column.fieldtype === "Int" ? 6 : 11, fit)}rem`;
}

const numberFormat = new Intl.NumberFormat(undefined, { maximumFractionDigits: 2 });

function cellText(row: Record<string, unknown>, column: GroupByColumn): string {
	const value = row[column.key];
	if (column.align === "right") {
		if (value === null || value === undefined) return "—";
		return typeof value === "number" ? numberFormat.format(value) : String(value);
	}
	if (value === null || value === undefined || value === "") return __("Not Set");
	if (column.fieldtype === "Check") return value ? __("Yes") : __("No");
	return String(value);
}
</script>
