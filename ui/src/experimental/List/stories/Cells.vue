<script setup lang="ts">
import { Avatar, Badge } from "frappe-ui";
import { List } from "../index";
import type { ListRowData } from "../types";
import { leadColumns, leads } from "./leads";

// The `cell` slot replaces the plain text for a column and keeps the row a link. The
// default text stays for every column the slot does not handle.
const statusTheme: Record<string, "gray" | "blue" | "green" | "amber"> = {
	Open: "gray",
	Contacted: "blue",
	Qualified: "amber",
	Converted: "green",
};

const currency = new Intl.NumberFormat("en-IN", {
	style: "currency",
	currency: "INR",
	maximumFractionDigits: 0,
});

function rowLink(row: ListRowData) {
	return { path: `/leads/${row.name}` };
}
</script>

<template>
	<div class="flex h-72 w-full flex-col">
		<List :columns="leadColumns" :rows="leads" :rowLink="rowLink" class="px-2">
			<template #cell="{ column, value }">
				<div
					v-if="column.fieldname === 'lead_name'"
					class="flex min-w-0 items-center gap-2"
				>
					<Avatar :label="value" size="sm" />
					<span class="truncate text-base text-ink-gray-8">{{ value }}</span>
				</div>
				<Badge
					v-else-if="column.fieldname === 'status'"
					:theme="statusTheme[value] ?? 'gray'"
					variant="subtle"
					:label="value"
				/>
				<span
					v-else-if="column.fieldname === 'annual_revenue'"
					class="tabular-nums text-base text-ink-gray-8"
				>
					{{ currency.format(Number(value)) }}
				</span>
				<div v-else class="truncate text-base text-ink-gray-8">{{ value }}</div>
			</template>
		</List>
	</div>
</template>
