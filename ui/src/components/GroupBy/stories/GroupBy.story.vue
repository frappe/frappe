<!--
  GroupBy demo — the control and the table against a live doctype, wired the way a
  host does it: `useGroupByData` fetches the groups for the control's model, and the
  rows go to `GroupByTable`, with the List module's footer paging through them. The
  doctype is typed in, so the story fetches nothing up front and names no app's
  doctypes. Story chrome uses frappe-ui
  components per the workspace convention.
-->
<template>
	<div class="flex h-[40rem] flex-col gap-4 p-6">
		<div class="flex items-center gap-4">
			<div class="flex items-center gap-2">
				<span class="text-p-sm text-ink-gray-6">Doctype</span>
				<TextInput
					v-model="typed"
					class="w-56"
					placeholder="Any doctype you can read"
					@change="doctype = typed.trim()"
				/>
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
import { Switch, TextInput } from "frappe-ui";
import { ListFooter } from "../../../experimental/List";
import { GroupBy, GroupByTable, serializeGroupBy, useGroupByData } from "../index";
import type { GroupBySettings } from "../types";

// Applied on change, not per keystroke, so half-typed names aren't fetched.
const typed = ref("");
const doctype = ref("");
const groupBy = ref<GroupBySettings | null>(null);
const hideLabel = ref(false);

const groups = useGroupByData(doctype, groupBy, []);

watch(doctype, () => (groupBy.value = null));
</script>
