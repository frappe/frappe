<script setup lang="ts">
import { ref } from "vue";
import { Button } from "frappe-ui";
import { ListBulkBar } from "../index";
import type { BulkAction } from "../types";

// The bar shows while `selection` has rows and floats over its `relative` host. Each
// action gets the selection; the clear button empties it.
const names = ["CRM-LEAD-0001", "CRM-LEAD-0002", "CRM-LEAD-0003"];
const selection = ref<string[]>([]);
const status = ref("");

const actions: BulkAction[] = [
	{ label: "Assign", onClick: (selected) => (status.value = `Assign ${selected.length}`) },
	{
		label: "Delete",
		theme: "red",
		onClick: (selected) => {
			status.value = `Delete ${selected.length}`;
			selection.value = [];
		},
	},
];
</script>

<template>
	<div class="flex w-full flex-col gap-3">
		<div class="flex gap-2">
			<Button label="Select one" @click="selection = names.slice(0, 1)" />
			<Button label="Select three" @click="selection = names" />
		</div>
		<div class="relative h-48 rounded-4 bg-surface-gray-1">
			<ListBulkBar v-model:selection="selection" :actions="actions" />
		</div>
		<p v-if="status" class="text-sm text-ink-gray-5">{{ status }}</p>
	</div>
</template>
