<script setup lang="ts">
import { computed, ref, watch } from "vue";
import { createResource } from "frappe-ui";
import { Filter } from "../../../components/Filter";
import { useFilters } from "../../../components/Filter/useFilters";
import { QuickFilter } from "../../../components/QuickFilter";
import { useQuickFilter } from "../../../components/QuickFilter/useQuickFilter";
import type { Sort } from "../../../components/SortBy/types";
import { List, ListFooter } from "../index";
import type { ListColumn, ListRowData } from "../types";

// The list with the two filter controls over it, against a live doctype. Both controls
// bind the same conditions, so a quick input and its dialog row stay in sync. The story
// fetches with the wire form of those conditions and the header sort; the page does
// the same with its own composable.
const doctype = "ToDo";
const columns: ListColumn[] = [
	{ fieldname: "name", label: "ID", width: "10rem" },
	{ fieldname: "status", label: "Status", width: "8rem" },
	{ fieldname: "priority", label: "Priority", width: "8rem" },
	{ fieldname: "allocated_to", label: "Allocated to" },
	{ fieldname: "reference_type", label: "Reference" },
	{ fieldname: "date", label: "Date", align: "right", width: "8rem" },
];

const filters = useFilters();
const quickFilter = useQuickFilter(doctype);
const sort = ref<Sort[]>([{ fieldname: "modified", direction: "desc" }]);
const pageSize = ref(20);
const limit = ref(20);
const selection = ref<string[]>([]);

const orderBy = computed(() => {
	const first = sort.value[0];
	return first ? `${first.fieldname} ${first.direction}` : "modified desc";
});

const rows = createResource({
	url: "frappe.client.get_list",
	makeParams: () => ({
		doctype,
		fields: columns.map((column) => column.fieldname),
		filters: filters.wire.value,
		order_by: orderBy.value,
		limit_page_length: limit.value,
	}),
	auto: true,
});

const count = createResource({
	url: "frappe.client.get_count",
	makeParams: () => ({ doctype, filters: filters.wire.value }),
	auto: true,
});

watch([filters.wire, orderBy], () => {
	limit.value = pageSize.value;
	rows.reload();
	count.reload();
});
watch(limit, () => rows.reload());

function rowLink(row: ListRowData) {
	return { path: `/todo/${row.name}` };
}
</script>

<template>
	<div class="flex h-[28rem] w-full flex-col gap-3">
		<div class="flex items-center gap-2">
			<QuickFilter
				class="flex-1"
				v-model:filters="filters.conditions.value"
				v-model:fields="quickFilter.fields.value"
				v-model:customizing="quickFilter.customizing.value"
				:doctype="doctype"
			/>
			<Filter v-model="filters.conditions.value" :doctype="doctype" />
		</div>
		<List
			v-model:selection="selection"
			v-model:sort="sort"
			:columns="columns"
			:rows="rows.data ?? []"
			:loading="rows.loading"
			:rowLink="rowLink"
			class="px-2"
		/>
		<ListFooter
			v-model:pageSize="pageSize"
			:rowCount="rows.data?.length ?? 0"
			:totalCount="count.data ?? 0"
			:hasCounts="count.data != null"
			class="px-2"
			@load-more="limit += pageSize"
			@page-size="limit = $event"
		/>
	</div>
</template>
