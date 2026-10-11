<!--
  The list table on frappe-ui's list molecule: a sticky header with sort and drag-resize, a
  checkbox column with select-all, and rows that are links. It fetches and stores nothing.
-->
<template>
	<ScrollArea
		ref="scroller"
		orientation="both"
		viewportClass="overscroll-y-none"
		class="min-h-0 flex-1"
	>
		<FrappeList
			divider="inset"
			:columns="tracks"
			:rowHeight="rowHeight"
			:style="{ '--list-row-padding-x': ROW_PADDING_X }"
			class="flex w-max min-w-full flex-col"
		>
			<ListHeader class="group sticky top-0 z-10 bg-surface-base">
				<div class="flex items-center justify-center" role="columnheader">
					<Checkbox
						:modelValue="selectAllState === 'all'"
						:indeterminate="selectAllState === 'some'"
						aria-label="Select all"
						@update:modelValue="toggleSelectAll"
					/>
				</div>
				<div
					v-for="column in columns"
					:key="column.fieldname"
					class="relative flex min-w-0"
					:class="alignClass(column)"
				>
					<ListHeaderCellSort
						v-if="sortable"
						class="min-w-0"
						:direction="directionFor(sort, column.fieldname)"
						:align="column.align === 'right' ? 'end' : 'start'"
						@click="sort = nextSort(sort, column.fieldname)"
					>
						{{ column.label }}
					</ListHeaderCellSort>
					<ListHeaderCell v-else class="min-w-0">{{ column.label }}</ListHeaderCell>
					<span
						class="absolute inset-y-0 -right-1 flex w-2 cursor-col-resize justify-center"
						@pointerdown.stop.prevent="startResize(column, $event)"
						@dblclick.stop.prevent="resetColumn(column)"
					>
						<span
							class="border-l border-outline-gray-2 opacity-0 transition-opacity group-hover:opacity-100"
							:class="{ 'opacity-100': resizingFieldname === column.fieldname }"
						/>
					</span>
				</div>
			</ListHeader>

			<div v-if="rows.length" ref="anchor" v-bind="wrapperProps" role="presentation">
				<ListRow
					v-for="{ data: row } in virtualRows"
					:key="rowValue(row)"
					:value="rowValue(row)"
					:to="rowLink?.(row)"
				>
					<!-- The molecule's own `selectable` turns a row click into a toggle; the row must stay
						a link, so the checkbox is drawn here (frappe/frappe-ui#1131). -->
					<ListCell class="justify-center">
						<div
							role="checkbox"
							:aria-checked="isSelected(rowValue(row))"
							:aria-label="`Select ${rowValue(row)}`"
							tabindex="0"
							@click.stop.prevent="toggle(rowValue(row))"
							@keydown.enter.stop.prevent="toggle(rowValue(row))"
							@keydown.space.stop.prevent="toggle(rowValue(row))"
						>
							<Checkbox
								:modelValue="isSelected(rowValue(row))"
								class="pointer-events-none"
								tabindex="-1"
								aria-hidden="true"
							/>
						</div>
					</ListCell>
					<ListCell
						v-for="column in columns"
						:key="column.fieldname"
						:class="alignClass(column)"
					>
						<slot
							name="cell"
							:row="row"
							:column="column"
							:value="cellText(row, column)"
						>
							<div class="truncate text-base text-ink-gray-8">
								{{ cellText(row, column) }}
							</div>
						</slot>
					</ListCell>
				</ListRow>
			</div>
			<template v-else-if="loading">
				<ListRow v-for="index in SKELETON_ROW_COUNT" :key="index">
					<ListCell />
					<ListCell v-for="column in skeletonColumns" :key="column.fieldname">
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
import { Checkbox, ScrollArea, Skeleton } from "frappe-ui";
import {
	List as FrappeList,
	ListCell,
	ListHeader,
	ListHeaderCell,
	ListHeaderCellSort,
	ListRow,
	useVirtualRows,
} from "frappe-ui/list";
import { computed, getCurrentInstance, ref, toRef } from "vue";
import type { Sort } from "../../components/SortBy/types";
import { columnTracks } from "./columnTracks";
import { directionFor, nextSort } from "./headerSort";
import { useColumnResize } from "./useColumnResize";
import { useRowSelection } from "./useRowSelection";
import type { ColumnResize, ListColumn, ListProps, ListRowData } from "./types";

const props = withDefaults(defineProps<ListProps>(), {
	columns: () => [],
	rows: () => [],
	rowKey: "name",
	loading: false,
	rowHeight: 40,
});

const selection = defineModel<string[]>("selection", { default: () => [] });
const sort = defineModel<Sort[]>("sort", { default: () => [] });

const emit = defineEmits<{
	"column-resize": [payload: ColumnResize];
	"column-reset": [payload: { fieldname: string }];
}>();

defineSlots<{
	cell?: (props: { row: ListRowData; column: ListColumn; value: string }) => unknown;
	empty?: () => unknown;
}>();

const ROW_PADDING_X = "0.5rem";
const SKELETON_ROW_COUNT = 10;
const SKELETON_COLUMN_COUNT = 4;

const scroller = ref<{ viewportElement: HTMLElement | null }>();

defineExpose({
	get viewportElement() {
		return scroller.value?.viewportElement ?? null;
	},
});

// Binding the sort model at mount is what makes the headers sortable, as the molecule's `active`.
const instance = getCurrentInstance();
const sortable = computed(() => "onUpdate:sort" in (instance?.vnode.props ?? {}));

const rows = toRef(props, "rows");
const columns = toRef(props, "columns");

// `ListRows virtual` looks for its scroll container before the viewport reports one, so the
// windowing takes the viewport directly (frappe/frappe-ui#1132).
const {
	rows: virtualRows,
	wrapperProps,
	anchor,
} = useVirtualRows(rows, {
	itemHeight: () => props.rowHeight,
	scrollContainer: () => scroller.value?.viewportElement ?? null,
});

function rowValue(row: ListRowData) {
	return String(row[props.rowKey]);
}

const { selectAllState, isSelected, toggle, toggleSelectAll } = useRowSelection(
	selection,
	rows,
	toRef(props, "rowKey")
);

const { drafts, resizingFieldname, startResize, resetColumn } = useColumnResize({
	onResize: (fieldname, width) => emit("column-resize", { fieldname, width }),
	onReset: (fieldname) => emit("column-reset", { fieldname }),
});

const skeletonColumns = computed<ListColumn[]>(() => {
	if (columns.value.length) return columns.value;
	return Array.from({ length: SKELETON_COLUMN_COUNT }, (_, index) => ({
		fieldname: `skeleton-${index}`,
		label: "",
	}));
});

const tracks = computed(() =>
	columnTracks(props.loading ? skeletonColumns.value : columns.value, drafts)
);

function cellText(row: ListRowData, column: ListColumn): string {
	const value = row[column.fieldname];
	if (value && typeof value === "object") {
		return String((value as { label?: unknown }).label ?? "");
	}
	return value == null ? "" : String(value);
}

function alignClass(column: ListColumn) {
	return column.align === "right" ? "justify-end" : "";
}
</script>

<style scoped>
:deep([data-slot="list-header-border"]) {
	grid-column: 2 / -1;
}

:deep([data-slot="list-row"]),
:deep([data-slot="list-header"]) {
	padding-inline-start: 0;
}

/* Without size containment the `fr` tracks resize whenever virtual scrolling swaps the
   mounted rows, since cell text feeds the list's max-content width. */
:deep([data-slot="list-cell"]) {
	contain: inline-size;
}
</style>
