<script setup lang="ts">
import { ref } from "vue";
import { Switch } from "frappe-ui";
import { ListFooter } from "../index";

// The page-size tabs bind `pageSize`; `page-size` fires only for a click, so a host can
// tell a choice from a programmatic set. Load More shows while rows remain. With
// `hasCounts` off the count is a skeleton, for the moment before `get_count` answers.
const hasCounts = ref(true);
const pageSize = ref(20);
const rowCount = ref(20);
const totalCount = 137;
</script>

<template>
	<div class="flex w-full flex-col gap-3">
		<label class="flex items-center gap-2 self-start text-sm text-ink-gray-6">
			Counts known
			<Switch v-model="hasCounts" />
		</label>
		<ListFooter
			v-model:pageSize="pageSize"
			:rowCount="rowCount"
			:totalCount="totalCount"
			:hasCounts="hasCounts"
			class="px-2"
			@load-more="rowCount = Math.min(rowCount + pageSize, totalCount)"
			@page-size="rowCount = Math.min($event, totalCount)"
		/>
	</div>
</template>
