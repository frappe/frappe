<!--
  GroupBy demo — the control and the table against a live doctype, wired the way a
  host does it: `useGroupByData` fetches the groups for the control's model, and the
  rows go to `GroupByTable`, with the List module's footer paging through them. The
  doctype picker lists the site's own doctypes. Story chrome uses frappe-ui
  components per the workspace convention.
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
				v-if="doctype"
				:key="doctype"
				v-model="groupBy"
				:doctype="doctype"
				:hideLabel="hideLabel"
				align="start"
			/>
		</div>

		<template v-if="doctype && groupBy">
			<GroupByTable
				:doctype="doctype"
				v-model:groupBy="groupBy"
				:rows="groups.rows.value"
				:totals="groups.totals.value"
				:loading="groups.loading.value"
			/>
			<ListFooter
				v-model:pageSize="groups.pageLength.value"
				:rowCount="groups.rowCount.value"
				:totalCount="groups.totalCount.value"
				:totalCapped="groups.totalCapped.value"
				:hasCounts="groups.hasCounts.value"
				:hasNextPage="groups.hasNextPage.value"
				@load-more="groups.loadMore"
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
import { GroupBy, GroupByTable, serializeGroupBy, useGroupByData } from "../index";
import type { GroupBySettings } from "../types";

// The site's own listable doctypes, so the story assumes no particular app.
const doctype = ref("");
const doctypeOptions = ref<string[]>([]);
createResource({
	url: "frappe.client.get_list",
	params: {
		doctype: "DocType",
		filters: { istable: 0, issingle: 0 },
		order_by: "name asc",
		limit_page_length: 0,
	},
	auto: true,
	onSuccess(rows: { name: string }[]) {
		doctypeOptions.value = rows.map((row) => row.name);
		doctype.value = doctypeOptions.value[0] ?? "";
	},
});
const groupBy = ref<GroupBySettings | null>(null);
const hideLabel = ref(false);

const groups = useGroupByData(doctype, groupBy, []);

watch(doctype, () => (groupBy.value = null));
</script>
