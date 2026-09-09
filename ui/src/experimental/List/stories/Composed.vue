<script setup lang="ts">
import { computed, ref } from "vue";
import { List, ListBulkBar, ListFooter } from "../index";
import type { Sort } from "../../../components/SortBy/types";
import type { BulkAction, ListRowData } from "../types";
import { leadColumns, manyLeads } from "./leads";

// The three together, as a list page lays them out: the table fills the frame, the
// footer sits under it, and the bulk bar floats over a `relative` host. The page owns
// the rows, the paging and what an action does; nothing here is fetched.
const all = manyLeads(137);
const pageSize = ref(20);
const shown = ref(20);
const selection = ref<string[]>([]);
const sort = ref<Sort[]>([{ fieldname: "lead_name", direction: "asc" }]);
const deleted = ref(0);

const rows = computed(() => all.slice(0, shown.value));

function rowLink(row: ListRowData) {
	return { path: `/leads/${row.name}` };
}

function loadMore() {
	shown.value = Math.min(shown.value + pageSize.value, all.length);
}

function choosePageSize(size: number) {
	shown.value = Math.min(size, all.length);
}

const actions: BulkAction[] = [
	{
		label: "Delete",
		theme: "red",
		onClick: (selected) => {
			deleted.value += selected.length;
			selection.value = [];
		},
	},
];
</script>

<template>
	<div class="relative flex h-96 w-full flex-col">
		<List
			v-model:selection="selection"
			v-model:sort="sort"
			:columns="leadColumns"
			:rows="rows"
			:rowLink="rowLink"
			class="px-2"
		/>
		<ListFooter
			v-model:pageSize="pageSize"
			:rowCount="rows.length"
			:totalCount="all.length"
			:hasCounts="true"
			class="px-2"
			@load-more="loadMore"
			@page-size="choosePageSize"
		/>
		<ListBulkBar v-model:selection="selection" :actions="actions" />
		<p v-if="deleted" class="mt-2 text-sm text-ink-gray-5">
			Delete asked for {{ deleted }} rows.
		</p>
	</div>
</template>
