<!--
  Isolated List demo on static rows: the sort and selection models, rows as links, the
  loading and empty states, and the resize events a host writes back into its columns.
-->
<template>
	<div class="flex h-[32rem] flex-col gap-4 p-6">
		<div class="flex items-center gap-4">
			<div class="flex items-center gap-2">
				<span class="text-p-sm text-ink-gray-6">Loading</span>
				<Switch v-model="loading" />
			</div>
			<div class="flex items-center gap-2">
				<span class="text-p-sm text-ink-gray-6">Empty</span>
				<Switch v-model="empty" />
			</div>
			<div class="flex items-center gap-2">
				<span class="text-p-sm text-ink-gray-6">Sortable</span>
				<Switch v-model="sortable" />
			</div>
		</div>

		<div class="flex min-h-0 flex-1 flex-col border border-outline-gray-1">
			<List
				v-if="sortable"
				v-model:selection="selection"
				v-model:sort="sort"
				:columns="columns"
				:rows="shownRows"
				:loading="loading"
				:rowLink="rowLink"
				class="px-5"
				@column-resize="resize"
				@column-reset="reset"
			/>
			<List
				v-else
				v-model:selection="selection"
				:columns="columns"
				:rows="shownRows"
				:loading="loading"
				:rowLink="rowLink"
				class="px-5"
				@column-resize="resize"
				@column-reset="reset"
			/>
		</div>

		<div class="flex flex-col gap-1 text-xs text-ink-gray-6">
			<div>Sort[] = {{ sort }}</div>
			<div>selection = {{ selection }}</div>
			<div>Column[] = {{ columns }}</div>
		</div>
	</div>
</template>

<script setup lang="ts">
import { computed, ref } from "vue";
import { Switch } from "frappe-ui";
import { applyColumnWidth, clearColumnWidth } from "../../ColumnSettings/columns";
import type { Sort } from "../../SortBy/types";
import { List } from "../index";
import type { ColumnResize, ListColumn, ListRowData } from "../types";

const loading = ref(false);
const empty = ref(false);
const sortable = ref(true);

const columns = ref<ListColumn[]>([
	{ fieldname: "lead_name", label: "Name" },
	{ fieldname: "status", label: "Status" },
	{ fieldname: "organization", label: "Organization" },
	{ fieldname: "annual_revenue", label: "Annual revenue", align: "right" },
]);

const rows: ListRowData[] = [
	{
		name: "CRM-LEAD-0001",
		lead_name: "Rosa Diaz",
		status: "Open",
		organization: "Nine-Nine",
		annual_revenue: 120000,
	},
	{
		name: "CRM-LEAD-0002",
		lead_name: "Jake Peralta",
		status: "Contacted",
		organization: "Nine-Nine",
		annual_revenue: 80000,
	},
	{
		name: "CRM-LEAD-0003",
		lead_name: "Amy Santiago",
		status: "Qualified",
		organization: "Binders Inc",
		annual_revenue: 250000,
	},
	{
		name: "CRM-LEAD-0004",
		lead_name: "Terry Jeffords",
		status: "Open",
		organization: "Yogurt Co",
		annual_revenue: 45000,
	},
	{
		name: "CRM-LEAD-0005",
		lead_name: "Raymond Holt",
		status: "Converted",
		organization: "Kevin & Co",
		annual_revenue: 900000,
	},
];

const shownRows = computed(() => (empty.value ? [] : rows));

const selection = ref<string[]>([]);
const sort = ref<Sort[]>([{ fieldname: "lead_name", direction: "asc" }]);

function rowLink(row: ListRowData) {
	return { path: `/leads/${row.name}` };
}

function resize({ fieldname, width }: ColumnResize) {
	columns.value = applyColumnWidth(columns.value, fieldname, width);
}

function reset({ fieldname }: { fieldname: string }) {
	columns.value = clearColumnWidth(columns.value, fieldname);
}
</script>
