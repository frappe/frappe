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
  CRM renders — fed by `serializeColumns` (`view.columns.wire`), so the drag math and
  grid layout come for free and stay pixel-parity with CRM. Rows are now LIVE: the
  host-side `useListData` turns the controls' wire projections (filters / order_by /
  fields) into `frappe.client.get_list` rows, so editing any control refetches.

  Selection and the footer are the host's job too — `selectable` turns on row
  checkboxes, `ListSelectBanner` surfaces bulk actions over the live selection, and
  `ListFooter` renders the count + Load More + page-length selector, paging through
  `useListData`. The shared composables stay fetch-free (ADR-0001); this surface owns
  the data + chrome around them.

  Mounted under the Shell story's `:key="doctype"`, so it (and `useListView`)
  reconstructs per doctype.
-->
<template>
	<ListViewShell :doctype="doctype" class="min-h-0 flex-1">
		<template #toolbar>
			<QuickFilter
				class="flex-1"
				v-model:filters="view.filters.conditions.value"
				v-model:fields="view.quickFilter.fields.value"
				v-model:customizing="view.quickFilter.customizing.value"
				:doctype="doctype"
			/>
			<!-- The right-side control cluster — Filter / Sort / Columns and the
			     "Customize Quick Filters" trigger — is the normal-mode chrome. Customize
			     mode is a focused, full-width editing surface, so the whole cluster is
			     hidden; QuickFilterCustomize carries its own Save affordance to exit. -->
			<template v-if="!view.quickFilter.customizing.value">
				<Filter v-model="view.filters.conditions.value" :doctype="doctype" />
				<SortBy v-model="view.sort.by.value" :doctype="doctype" />
				<ColumnSettings
					v-model="view.columns.shown.value"
					:doctype="doctype"
					:synthetic="view.columns.synthetic.value"
					:can-reset="view.columns.isCustomized.value"
					@reset="view.columns.reset()"
				/>
				<Button
					v-if="view.quickFilter.canCustomize.value"
					icon="lucide-settings-2"
					tooltip="Customize Quick Filters"
					variant="ghost"
					@click="view.quickFilter.customizing.value = true"
				/>
			</template>
		</template>

		<template #table>
			<!-- `min-h-0` lets the list shrink inside the flex table region so its own
			     `ListRows` (`overflow-y-auto`) becomes the scroller, not the page. -->
			<ListView
				class="min-h-0"
				:columns="view.columns.wire.value"
				:rows="data.rows.value"
				row-key="name"
				:options="{ selectable: true, showTooltip: false, resizeColumn: true }"
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
				<!-- The synthetic column (ADR-0033) carries no docfield value — the HOST draws
				     its cell. A production host (frappe-os) resolves a per-row Record indicator
				     here; this story renders a representative badge to show the "library carries
				     the column, host owns the cell" half of the seam. Every other cell renders
				     its value as before. -->
				<template #cell="{ column, item }">
					<Badge
						v-if="column.type === 'Status'"
						:label="column.label"
						theme="green"
						variant="subtle"
					/>
					<span v-else class="text-base">{{ item }}</span>
				</template>
				<!-- The selection banner lives in the default-slot fallback we're
				     overriding, so the host re-adds it. Its `#actions` slot is where
				     bulk actions go; these are demo no-ops (a real host would mutate). -->
				<ListSelectBanner>
					<template #actions="{ selections: selected, unselectAll }">
						<Dropdown :options="bulkActions(selected, unselectAll)">
							<Button icon="lucide-more-horizontal" variant="ghost" />
						</Dropdown>
					</template>
				</ListSelectBanner>
			</ListView>
		</template>

		<template #footer>
			<!-- Real list footer: page-length selector (left), Load More + "N of total"
			     (right). `v-model` is the page length — a change refetches page 1. -->
			<ListFooter
				v-model="data.pageLength.value"
				:options="{ rowCount: data.rowCount.value, totalCount: data.totalCount.value }"
				@loadMore="data.loadMore()"
			/>
			<!-- The dev wire-output readout this surface was built to verify. -->
			<div class="mt-2 space-y-0.5 border-t border-outline-gray-1 pt-2">
				<div class="text-xs text-ink-gray-5">
					order_by = "{{ view.sort.orderBy.value }}"
				</div>
				<div class="text-xs text-ink-gray-5">filters = {{ view.filters.wire.value }}</div>
				<div class="text-xs text-ink-gray-5">columns = {{ view.columns.wire.value }}</div>
			</div>
		</template>
	</ListViewShell>
</template>

<script setup lang="ts">
import {
	Badge,
	Button,
	Dropdown,
	ListView,
	ListHeader,
	ListRows,
	ListSelectBanner,
	ListFooter,
	toast,
} from "frappe-ui";
import { computed, onMounted, watch } from "vue";
import { ListViewShell } from "../index";
import { useListView } from "../useListView";
import { useListData } from "../useListData";
import { Filter } from "../../Filter";
import { SortBy } from "../../SortBy";
import { QuickFilter } from "../../QuickFilter";
import { ColumnSettings } from "../../ColumnSettings";
import type { SyntheticColumn } from "../../ColumnSettings";

const props = defineProps<{ doctype: string; syntheticDemo?: boolean }>();

// A demo synthetic column (ADR-0033) — the Record indicator, the OS's first synthetic
// column — declared by the host and folded into the column state: after the title,
// subsuming the raw `status` docfield. Reactive, so the Shell's toggle folds it in/out
// live; `useColumns` takes it as a getter. Off ⇒ no declaration ⇒ identical behaviour.
const synthetic = computed<SyntheticColumn[]>(() =>
	props.syntheticDemo
		? [
				{
					key: "_indicator",
					label: "Status",
					type: "Status",
					place: "after-title",
					subsumes: "status",
				},
		  ]
		: []
);

// `view.quickFilter.customizing` / `.canCustomize` come from the shared composable,
// so the toggle below works regardless of where it sits — no template ref needed.
const view = useListView(props.doctype, { synthetic });
// The host owns fetching: `useListData` turns the controls' wire projections into
// live `get_list` rows + total, and pages via the footer.
const data = useListData(props.doctype, view);

// Layout persistence via the `snapshot` / `restore()` seam (ADR-0007). The library
// owns no saving; the host picks when and where. Restore on mount seeds every control
// at once (filters, sort, columns + widths, quick-filter fields) from one object.
const storageKey = `listview:${props.doctype}`;

onMounted(() => {
	const saved = localStorage.getItem(storageKey);
	if (saved) view.restore(JSON.parse(saved));
});

// Autosave on ANY change — filter, sort, column add/remove/resize, quick filter.
// `view.snapshot` is a fresh object only on a real edit, so this one watcher persists
// the lot (no per-control wiring). A real host swaps the body for its save RPC; the
// debounce keeps a drag-resize from writing on every pixel. The story uses
// localStorage to prove the round-trip.
let saveTimer: ReturnType<typeof setTimeout>;
watch(view.snapshot, (snap) => {
	clearTimeout(saveTimer);
	saveTimer = setTimeout(() => {
		localStorage.setItem(storageKey, JSON.stringify(snap));
	}, 500);
});

// Demo bulk actions. A real host mutates here (bulk edit/delete/assign); the story
// just confirms the selection set reaches an action handler and clears after.
function bulkActions(selected: Set<string>, unselectAll: () => void) {
	const run = (verb: string) => () => {
		toast.success(`${verb} ${selected.size} ${props.doctype} (demo)`);
		unselectAll();
	};
	return [
		{ label: "Edit", onClick: run("Edit") },
		{ label: "Delete", onClick: run("Delete") },
	];
}

// frappe-ui's `ListHeaderItem` emits `{ key, width, save }` as a column is dragged.
// The composite owns the handler (ADR-0006); we ignore the `save` debounce flag —
// persistence is the host's job — and just write the width into the shared ref.
function onColumnWidthUpdated(event: { key: string; width: string }) {
	view.columns.setWidth(event.key, event.width);
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
	const column = view.columns.wire.value[index];
	if (column) view.columns.resetWidth(column.key);
}
</script>
