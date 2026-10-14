<!--
  GroupBy demo — the control and the table against a live doctype, wired the way a
  host does it: the control's model goes through `serializeGroupBy` into
  `frappe.client.get_list`, and the rows go to `GroupByTable`, with the List module's
  footer paging through the groups. Story chrome uses frappe-ui components per the
  workspace convention.
-->
<template>
	<div class="flex h-[40rem] flex-col gap-4 p-6">
		<div class="flex items-center gap-4">
			<div class="flex items-center gap-2">
				<span class="text-p-sm text-ink-gray-6">Doctype</span>
				<Select v-model="doctype" :options="doctypeOptions" class="w-56" />
			</div>
			<div class="flex items-center gap-2">
				<span class="text-p-sm text-ink-gray-6">Hide label</span>
				<Switch v-model="hideLabel" />
			</div>
			<GroupBy
				:key="doctype"
				v-model="groupBy"
				:doctype="doctype"
				:hideLabel="hideLabel"
				align="start"
			/>
		</div>

		<template v-if="groupBy">
			<GroupByTable
				:doctype="doctype"
				:groupBy="groupBy"
				:rows="groups.data ?? []"
				:loading="groups.loading"
			/>
			<ListFooter
				v-model:pageSize="pageSize"
				:rowCount="groups.data?.length ?? 0"
				:totalCount="groupCount.data?.length ?? 0"
				:hasCounts="Boolean(groupCount.data)"
				@load-more="limit += pageSize"
			/>
		</template>

		<div class="flex flex-col gap-1 text-xs text-ink-gray-6">
			<div>GroupBySettings = {{ groupBy }}</div>
			<div v-if="groupBy">get_list args = {{ serializeGroupBy(groupBy) }}</div>
		</div>
	</div>
</template>

<script setup lang="ts">
import { ref, watch } from "vue";
import { Select, Switch, createResource } from "frappe-ui";
import { ListFooter } from "../../../experimental/List";
import { GroupBy, GroupByTable, serializeGroupBy } from "../index";
import type { GroupBySettings } from "../types";

const doctypeOptions = ["CRM Lead", "CRM Deal", "CRM Task", "ToDo"];
const doctype = ref("CRM Deal");
const groupBy = ref<GroupBySettings | null>(null);
const hideLabel = ref(false);
const pageSize = ref(20);
const limit = ref(20);

const groups = createResource({
	url: "frappe.client.get_list",
	makeParams: () => ({
		doctype: doctype.value,
		...serializeGroupBy(groupBy.value as GroupBySettings),
		limit_page_length: limit.value,
	}),
});

// The footer's total is the number of groups, so fetch just the group keys.
const groupCount = createResource({
	url: "frappe.client.get_list",
	makeParams: () => ({
		doctype: doctype.value,
		fields: groupBy.value?.fields,
		group_by: groupBy.value?.fields.join(", "),
		limit_page_length: 0,
	}),
});

watch(doctype, () => (groupBy.value = null));
watch(pageSize, (size) => (limit.value = size));
watch(groupBy, () => {
	limit.value = pageSize.value;
	if (groupBy.value) groupCount.reload();
});
watch([groupBy, limit], () => groupBy.value && groups.reload(), { deep: true });
</script>
