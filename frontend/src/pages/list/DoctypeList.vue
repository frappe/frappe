<!--
  One doctype's list in the frame: the quick filter and the controls in one row under the title,
  then the table with its bulk bar and footer. The composable holds the state; this lays it out.
-->
<template>
	<PageFrame :scroll="false">
		<template #header>
			<PageHeaderTitle :title="doctype" />
		</template>

		<p v-if="metaError" :class="pageGutter" class="py-5 text-sm text-ink-red-4">
			{{ metaError }}
		</p>

		<template v-else>
			<div
				:class="pageGutter"
				class="flex shrink-0 items-start justify-between gap-2 pt-3.5"
			>
				<div class="flex min-w-0 flex-1 flex-col">
					<QuickFilter
						v-model:filters="filters"
						v-model:fields="quickFilterFields"
						v-model:customizing="customizing"
						:doctype="doctype"
					/>
				</div>
				<div v-if="!customizing" class="flex shrink-0 items-center gap-2">
					<Filter v-model="filters" :doctype="doctype" />
					<SortBy v-model="sort" :doctype="doctype" />
					<ColumnSettings
						v-model="columns"
						:doctype="doctype"
						:canReset="columnsCustomized"
						@reset="resetColumns"
					/>
					<Dropdown :options="menuOptions" side="bottom" align="end">
						<div class="flex shrink-0">
							<Button icon="lucide-ellipsis" label="More" />
						</div>
					</Dropdown>
				</div>
			</div>

			<div class="relative flex min-h-0 flex-1 flex-col pt-2">
				<p v-if="error" :class="pageGutter" class="text-sm text-ink-red-4">
					{{ error.message }}
				</p>
				<List
					v-else
					ref="table"
					v-model:selection="selection"
					v-model:sort="sort"
					:columns="columns"
					:rows="rows"
					:loading="loading"
					:rowLink="rowLink"
					gutter="var(--page-gutter)"
					@column-resize="resizeColumn($event.fieldname, $event.width)"
					@column-reset="resetColumnWidth($event.fieldname)"
				/>
				<ListBulkBar v-model:selection="selection" :actions="bulkActions" />
				<ListFooter
					v-model:pageSize="pageSize"
					:class="pageGutter"
					:rowCount="rowCount"
					:totalCount="totalCount"
					:totalCapped="totalCapped"
					:hasCounts="hasCounts"
					:hasNextPage="hasNextPage"
					@load-more="next"
				/>
			</div>
		</template>

		<DeleteDialog
			v-model="confirmingDelete"
			:count="selection.length"
			:run="deleteSelection"
		/>
	</PageFrame>
</template>

<script setup lang="ts">
import { Button, Dropdown, PageHeaderTitle } from "frappe-ui";
import { ColumnSettings } from "@framework/ui/ColumnSettings";
import { List, ListBulkBar, ListFooter, type BulkAction } from "@framework/ui/experimental/List";
import { Filter } from "@framework/ui/Filter";
import { QuickFilter } from "@framework/ui/QuickFilter";
import { SortBy } from "@framework/ui/SortBy";
import { ref } from "vue";
import { useListPage } from "@/list/useListPage";
import { useScrollMemory } from "@/list/useScrollMemory";
import PageFrame, { pageGutter } from "@/shell/PageFrame.vue";
import DeleteDialog from "./DeleteDialog.vue";

const props = defineProps<{ doctype: string }>();

const {
	filters,
	sort,
	columns,
	quickFilterFields,
	customizing,
	selection,
	pageSize,
	rowsKey,
	rows,
	loading,
	error,
	metaError,
	rowCount,
	totalCount,
	totalCapped,
	hasCounts,
	hasNextPage,
	next,
	columnsCustomized,
	resetColumns,
	resizeColumn,
	resetColumnWidth,
	rowLink,
	deleteSelection,
} = useListPage(props.doctype);

const table = ref<{ viewportElement: HTMLElement | null } | null>(null);
const confirmingDelete = ref(false);

useScrollMemory(
	() => table.value?.viewportElement ?? null,
	() => rows.value.length > 0,
	{ doctype: props.doctype, query: rowsKey }
);

const menuOptions = [
	{
		label: "Customize Quick Filter",
		icon: "lucide-sliders-horizontal",
		onClick: () => (customizing.value = true),
	},
];

const bulkActions: BulkAction[] = [
	{ label: "Delete", theme: "red", onClick: () => (confirmingDelete.value = true) },
];
</script>
