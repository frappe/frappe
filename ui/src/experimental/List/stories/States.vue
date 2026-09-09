<script setup lang="ts">
import { computed, ref } from "vue";
import { Button, TabButtons } from "frappe-ui";
import { List } from "../index";
import { leadColumns, leads } from "./leads";

// `loading` with no rows draws skeleton rows in the column tracks. No rows and not
// loading draws the `empty` slot; the default is a "No records" line.
const state = ref<"rows" | "loading" | "empty">("rows");
const options = [
	{ label: "Rows", value: "rows" },
	{ label: "Loading", value: "loading" },
	{ label: "Empty", value: "empty" },
];
const rows = computed(() => (state.value === "rows" ? leads : []));
</script>

<template>
	<div class="flex h-80 w-full flex-col gap-3">
		<TabButtons v-model="state" :options="options" class="self-start" />
		<List :columns="leadColumns" :rows="rows" :loading="state === 'loading'" class="px-2">
			<template #empty>
				<div class="flex flex-col items-center gap-2 py-16 text-center">
					<span class="text-base font-medium text-ink-gray-7">No leads yet</span>
					<span class="text-sm text-ink-gray-5"
						>Leads you create or import show here.</span
					>
					<Button label="New lead" variant="subtle" class="mt-1" />
				</div>
			</template>
		</List>
	</div>
</template>
