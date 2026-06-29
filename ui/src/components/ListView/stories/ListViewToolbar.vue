<!--
  The list-view integration surface — constructs the shared `useListView` state and
  mounts the extracted controls into the `ListViewShell`. Filter and QuickFilter both
  bind the SAME `filters` ref (the composable's SoT), so setting a quick input updates
  the matching filter condition and vice versa with no wiring here. ColumnSettings and
  the table's drag-resize likewise share the SAME `columns` ref (ADR-0006): editing a
  width in the popover resizes the header track, and dragging the header writes the
  width back into the popover — both via `view.columns`, no event plumbing here beyond
  handing the frappe-ui `columnWidthUpdated` event to the composite's handler.

  The `#table` slot mounts frappe-ui's own `ListView`/`ListHeader` — the same chrome
  CRM renders — fed by `serializeColumns` (`view.wireColumns`), so the drag math and
  grid layout come for free and stay pixel-parity with CRM. Rows are stubbed (no
  `get_list`); this surface proves the controls + sync, not data fetching.

  Mounted under the Shell story's `:key="doctype"`, so it (and `useListView`)
  reconstructs per doctype.
-->
<template>
	<ListViewShell :doctype="doctype">
		<template #toolbar>
			<QuickFilter
				class="flex-1"
				v-model:filters="view.filters.value"
				v-model:fields="view.quickFilterFields.value"
				v-model:customizing="view.customizing.value"
				:doctype="doctype"
			/>
			<Filter v-model="view.filters.value" :doctype="doctype" />
			<SortBy v-model="view.sorts.value" :doctype="doctype" />
			<ColumnSettings
				v-model="view.columns.value"
				:doctype="doctype"
				:can-reset="view.isColumnsCustomized.value"
				@reset="view.resetColumns()"
			/>
			<Button
				v-if="view.canCustomize.value"
				:icon="view.customizing.value ? 'lucide-check' : 'lucide-settings-2'"
				:tooltip="view.customizing.value ? 'Done' : 'Customize Quick Filters'"
				:variant="view.customizing.value ? 'subtle' : 'ghost'"
				@click="view.customizing.value = !view.customizing.value"
			/>
		</template>

		<template #table>
			<ListView
				:columns="view.wireColumns.value"
				:rows="stubRows"
				row-key="name"
				:options="{ selectable: false, showTooltip: false, resizeColumn: true }"
			>
				<!-- Explicit default slot: frappe-ui's `ListView` does NOT re-emit
				     `columnWidthUpdated`, so we catch it on `ListHeader` ourselves and
				     hand it to the composite's resize handler. The native `dblclick`
				     falls through to the header's grid root, where we delegate the
				     reset-to-auto gesture (frappe-ui exposes no dblclick on the resizer). -->
				<ListHeader
					@columnWidthUpdated="onColumnWidthUpdated"
					@dblclick="onResizerDoubleClick"
				/>
				<ListRows />
			</ListView>
		</template>

		<template #footer>
			<div class="text-xs text-ink-gray-6">order_by = "{{ view.orderBy.value }}"</div>
			<div class="text-xs text-ink-gray-6">filters = {{ view.wireFilters.value }}</div>
			<div class="text-xs text-ink-gray-6">columns = {{ view.wireColumns.value }}</div>
		</template>
	</ListViewShell>
</template>

<script setup lang="ts">
import { computed } from "vue";
import { Button, ListView, ListHeader, ListRows } from "frappe-ui";
import { ListViewShell } from "../index";
import { useListView } from "../useListView";
import { Filter } from "../../Filter";
import { SortBy } from "../../SortBy";
import { QuickFilter } from "../../QuickFilter";
import { ColumnSettings } from "../../ColumnSettings";

const props = defineProps<{ doctype: string }>();
// `view.customizing` / `view.canCustomize` come from the shared composable, so the
// toggle below works regardless of where it sits — no template ref needed.
const view = useListView(props.doctype);

// frappe-ui's `ListHeaderItem` emits `{ key, width, save }` as a column is dragged.
// The composite owns the handler (ADR-0006); we ignore the `save` debounce flag —
// persistence is the host's job — and just write the width into the shared ref.
function onColumnWidthUpdated(event: { key: string; width: string }) {
	view.setColumnWidth(event.key, event.width);
}

// frappe-ui's `ListHeaderItem` binds drag-resize to the resizer's `mousedown` but
// exposes neither a dblclick nor its `startResizing`, so we delegate the
// double-click-to-reset gesture on the header grid: find the double-clicked
// resizer, map its position to a column, and clear that column's width back to
// auto (so it flexes to fill again).
function onResizerDoubleClick(event: MouseEvent) {
	const resizer = (event.target as HTMLElement).closest(".cursor-col-resize");
	const header = resizer?.closest(".grid");
	if (!resizer || !header) return;
	const index = Array.from(header.querySelectorAll(".cursor-col-resize")).indexOf(resizer);
	const column = view.wireColumns.value[index];
	if (column) view.resetColumnWidth(column.key);
}

// Stub rows so the table renders real header chrome (the resize target) without a
// `get_list`. Each row fills every shown column's key with a placeholder cell.
const stubRows = computed(() =>
	[1, 2, 3].map((n) => {
		const row: Record<string, unknown> = { name: `row-${n}` };
		for (const column of view.wireColumns.value) {
			row[column.key] = `${column.label} ${n}`;
		}
		return row;
	})
);
</script>
