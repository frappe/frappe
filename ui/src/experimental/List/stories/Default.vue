<script setup lang="ts">
import { ref } from "vue";
import { List } from "../index";
import type { Sort } from "../../../components/SortBy/types";
import type { ListRowData } from "../types";
import { leadColumns, leads } from "./leads";

// Rows are links: `rowLink` returns the route a row opens. Binding `sort` is what
// makes the headers sortable; a click sets that column as the whole sort.
const selection = ref<string[]>([]);
const sort = ref<Sort[]>([{ fieldname: "lead_name", direction: "asc" }]);

function rowLink(row: ListRowData) {
	return { path: `/leads/${row.name}` };
}
</script>

<template>
	<div class="flex h-72 w-full flex-col">
		<List
			v-model:selection="selection"
			v-model:sort="sort"
			:columns="leadColumns"
			:rows="leads"
			:rowLink="rowLink"
			class="px-2"
		/>
		<p class="mt-3 text-sm text-ink-gray-5">
			sort {{ sort[0]?.fieldname }} {{ sort[0]?.direction }} · selected
			{{ selection.length }}
		</p>
	</div>
</template>
