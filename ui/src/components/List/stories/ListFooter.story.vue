<!-- Isolated ListFooter demo: the counts, Load More, and the page-size model against its emit. -->
<template>
	<div class="flex flex-col gap-4 p-6">
		<div class="flex items-center gap-4">
			<div class="flex items-center gap-2">
				<span class="text-p-sm text-ink-gray-6">Counts known</span>
				<Switch v-model="hasCounts" />
			</div>
			<div class="flex items-center gap-2">
				<span class="text-p-sm text-ink-gray-6">Total</span>
				<Select v-model="totalCount" :options="totalOptions" class="w-28" />
			</div>
		</div>

		<div class="border border-outline-gray-1">
			<ListFooter
				v-model:pageSize="pageSize"
				class="px-5"
				:rowCount="rowCount"
				:totalCount="totalCount"
				:hasCounts="hasCounts"
				@load-more="rowCount = Math.min(rowCount + pageSize, totalCount)"
				@page-size="chosen.push($event)"
			/>
		</div>

		<div class="flex flex-col gap-1 text-xs text-ink-gray-6">
			<div>pageSize = {{ pageSize }}</div>
			<div>page-size emits = {{ chosen }}</div>
		</div>
	</div>
</template>

<script setup lang="ts">
import { ref } from "vue";
import { Select, Switch } from "frappe-ui";
import { ListFooter } from "../index";

const totalOptions = [
	{ label: "20", value: 20 },
	{ label: "50", value: 50 },
	{ label: "1200", value: 1200 },
];
const hasCounts = ref(true);
const totalCount = ref(50);
const rowCount = ref(20);
const pageSize = ref(20);
const chosen = ref<number[]>([]);
</script>
