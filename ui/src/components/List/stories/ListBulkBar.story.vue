<!-- Isolated ListBulkBar demo: it floats over a relative host and shows only while rows are selected. -->
<template>
	<div class="flex flex-col gap-4 p-6">
		<div class="flex items-center gap-2">
			<Button label="Select two" @click="selection = ['CRM-LEAD-0001', 'CRM-LEAD-0002']" />
			<Button label="Select five" @click="selection = names" />
		</div>

		<div class="relative h-64 border border-outline-gray-1 bg-surface-gray-1">
			<ListBulkBar v-model:selection="selection" :actions="actions" />
		</div>

		<div class="flex flex-col gap-1 text-xs text-ink-gray-6">
			<div>selection = {{ selection }}</div>
			<div>last action = {{ lastAction }}</div>
		</div>
	</div>
</template>

<script setup lang="ts">
import { ref } from "vue";
import { Button } from "frappe-ui";
import { ListBulkBar } from "../index";
import type { BulkAction } from "../types";

const names = [
	"CRM-LEAD-0001",
	"CRM-LEAD-0002",
	"CRM-LEAD-0003",
	"CRM-LEAD-0004",
	"CRM-LEAD-0005",
];
const selection = ref<string[]>([]);
const lastAction = ref("");

const actions: BulkAction[] = [
	{
		label: "Delete",
		theme: "red",
		onClick: (selected) => {
			lastAction.value = `Delete ${selected.length}`;
			selection.value = [];
		},
	},
];
</script>
