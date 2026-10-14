<!--
  GroupByTable — one row per group: the grouped fields, then one right-aligned column
  per aggregate. It fetches and stores nothing; the host runs the `serializeGroupBy`
  query and passes the rows in. Rows match the List module's height and dividers, so
  a grouped list reads like the list it summarizes.

  The `#cell` slot gets `{ row, column, value }` so a host can draw what the library
  can't know, like user avatars or a currency symbol.
-->
<template>
	<ScrollArea orientation="both" class="min-h-0 flex-1">
		<FrappeList
			divider="full"
			:columns="tracks"
			:rowHeight="rowHeight"
			:style="{ '--list-row-padding-x': '0.5rem' }"
			class="flex w-max min-w-full flex-col"
		>
			<ListHeader class="sticky top-0 z-10 bg-surface-base">
				<ListHeaderCell
					v-for="column in columns"
					:key="column.key"
					:class="column.align === 'right' ? 'justify-end' : ''"
				>
					{{ column.label }}
				</ListHeaderCell>
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
					<span class="text-base font-medium text-ink-gray-7">No records</span>
				</div>
			</slot>
		</FrappeList>
	</ScrollArea>
</template>

<script setup lang="ts">
import { ScrollArea, Skeleton } from "frappe-ui";
import { List as FrappeList, ListCell, ListHeader, ListHeaderCell, ListRow } from "frappe-ui/list";
import { computed } from "vue";
import { useDoctypeMeta } from "../../composables/useDoctypeMeta";
import {
	AGGREGATE_FUNCTIONS,
	aggregateKey,
	findGroupByField,
	isCompleteAggregate,
} from "./groupBy";
import type { GroupByColumn, GroupByTableProps } from "./types";

const props = withDefaults(defineProps<GroupByTableProps>(), {
	loading: false,
	rowHeight: 40,
});

const { meta } = useDoctypeMeta(() => props.doctype);
const metaFields = computed(() => meta.value?.fields ?? []);

const columns = computed<GroupByColumn[]>(() => [
	...props.groupBy.fields.map((fieldname) => {
		const field = findGroupByField(metaFields.value, fieldname);
		return {
			key: fieldname,
			label: field?.label ?? fieldname,
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
			label: a.function === "count" ? "Count" : `${fn} of ${field?.label ?? a.fieldname}`,
			align: "right" as const,
			fieldtype: a.function === "count" ? "Int" : field?.fieldtype,
			options: field?.options,
		};
	}),
]);

// Group columns size to their values within a range; aggregates stay narrow so each
// number sits next to its label, and a last flexible track takes the leftover width.
const tracks = computed(() => [
	...columns.value.map((c) =>
		c.align === "left" ? "minmax(10rem, 18rem)" : c.fieldtype === "Int" ? "6rem" : "11rem"
	),
	"minmax(0, 1fr)",
]);

const numberFormat = new Intl.NumberFormat(undefined, { maximumFractionDigits: 2 });

function cellText(row: Record<string, unknown>, column: GroupByColumn): string {
	const value = row[column.key];
	if (column.align === "right") {
		if (value === null || value === undefined) return "—";
		return typeof value === "number" ? numberFormat.format(value) : String(value);
	}
	if (value === null || value === undefined || value === "") return "Not Set";
	if (column.fieldtype === "Check") return value ? "Yes" : "No";
	return String(value);
}
</script>
