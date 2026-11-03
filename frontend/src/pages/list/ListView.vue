<!--
  The List type's renderer: the table with its bulk bar and footer, and the column settings among
  the page's controls. The composable holds the state; this lays it out.
-->
<template>
	<Teleport v-if="host.controls.value" :to="host.controls.value">
		<ColumnSettings
			v-model="columns"
			:doctype="view.doctype"
			:canReset="columnsCustomized"
			@reset="resetColumns"
		/>
	</Teleport>
	<PageState v-if="error" v-bind="failedState(error, reload)" />
	<List
		v-else
		ref="table"
		v-model:selection="selection"
		v-model:sort="sort"
		:columns="columns"
		:rows="rows"
		:loading="loading"
		:rowLink="rowLink"
		:rowMenu="rowActions.length > 0"
		gutter="var(--page-gutter)"
		@column-resize="resizeColumn($event.fieldname, $event.width)"
		@column-reset="resetColumnWidth($event.fieldname)"
	>
		<template #cell="{ row, column, value }">
			<EmailCell
				v-if="emailFields.has(column.fieldname)"
				:field="emailFields.get(column.fieldname)!"
				:value="value"
				:doctype="view.doctype"
				:name="row.name"
			/>
			<PhoneCell
				v-else-if="phoneFields.has(column.fieldname)"
				:field="phoneFields.get(column.fieldname)!"
				:value="value"
			/>
			<div v-else class="truncate text-base text-ink-gray-8">{{ value }}</div>
		</template>
		<template v-if="rowActions.length" #rowMenu="{ row }">
			<RowMenu :options="rowMenuOptions(row, rowActions, listActs)" />
		</template>
		<template #empty>
			<PageState :name="filters.length ? 'filtered' : 'empty'" />
		</template>
	</List>
	<ListBulkBar v-model:selection="selection" :actions="bulkActions" />
	<ListFooter
		v-model:pageSize="pageSize"
		:class="pageGutter"
		:rowCount="rowCount"
		:totalCount="totalCount"
		:totalCapped="totalCapped"
		:totalUnknown="totalUnknown"
		:hasCounts="hasCounts"
		:hasNextPage="hasNextPage"
		@load-more="next"
		@page-size="show"
		@count="countExact"
	/>

	<DeleteDialog v-model="confirmingDelete" :count="selection.length" :run="deleteSelection" />
</template>

<script setup lang="ts">
import { ColumnSettings } from "@framework/ui/ColumnSettings";
import { isEmailField, isPhoneField } from "@framework/ui/fields";
import type { RawMetaField } from "@framework/ui/FormLayout";
import { List, ListBulkBar, ListFooter, type BulkAction } from "@framework/ui/experimental/List";
import { computed, ref } from "vue";
import { __ } from "@/i18n";
import { useListView } from "@/list/useListView";
import { useScrollMemory } from "@/list/useScrollMemory";
import type { View } from "@/list/view";
import { pageGutter } from "@/shell/PageFrame.vue";
import { failedState } from "@/shell/pageState";
import PageState from "@/shell/PageState.vue";
import DeleteDialog from "./DeleteDialog.vue";
import type { RendererHost } from "./renderer";
import EmailCell from "./EmailCell.vue";
import PhoneCell from "./PhoneCell.vue";
import RowMenu from "./RowMenu.vue";
import { rowActionEntries, rowMenuOptions } from "./rowActions";

const props = defineProps<{ view: View; host: RendererHost }>();
const { filters, sort } = props.view;

const {
	columns,
	rowActions,
	fieldOf,
	selection,
	pageSize,
	rowsKey,
	rows,
	loading,
	error,
	rowCount,
	totalCount,
	totalCapped,
	totalUnknown,
	hasCounts,
	hasNextPage,
	next,
	show,
	countExact,
	columnsCustomized,
	resetColumns,
	resizeColumn,
	resetColumnWidth,
	rowLink,
	reload,
	deleteSelection,
} = useListView(props.view);

props.host.onCreate(reload);

const table = ref<{ viewportElement: HTMLElement | null } | null>(null);
const confirmingDelete = ref(false);

useScrollMemory(
	() => table.value?.viewportElement ?? null,
	() => rows.value.length > 0,
	{ doctype: props.view.doctype, query: rowsKey }
);

const phoneFields = computed(() => columnFields(isPhoneField));
const emailFields = computed(() => columnFields(isEmailField));

function columnFields(matches: (field: RawMetaField) => boolean) {
	const fields = new Map<string, RawMetaField>();
	for (const { fieldname } of columns.value) {
		const field = fieldOf(fieldname);
		if (field && matches(field)) fields.set(fieldname, field);
	}
	return fields;
}

const listActs = props.host.acts(() => [
	...(selection.value.length ? [deleteEntry()] : []),
	...rowActionEntries(rowActions),
]);

function deleteEntry() {
	return {
		item: {
			name: "delete",
			label: __("Delete"),
			icon: "lucide-trash-2",
			right: "delete",
			run: () => (confirmingDelete.value = true),
		},
		hidden: false,
	};
}

const deleteAct = computed(() => listActs.drawn("delete"));

const bulkActions = computed<BulkAction[]>(() => {
	const act = deleteAct.value;
	return act ? [{ label: act.label!, theme: "red", onClick: () => listActs.perform(act) }] : [];
});
</script>
