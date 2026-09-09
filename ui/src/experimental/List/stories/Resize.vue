<script setup lang="ts">
import { ref } from "vue";
import { applyColumnWidth, clearColumnWidth } from "../../../components/ColumnSettings/columns";
import { List } from "../index";
import type { ColumnResize, ListColumn } from "../types";
import { leads } from "./leads";

// Drag the handle at a header's right edge to resize; double-click it to reset. `List`
// keeps no width of its own: it emits, and the host writes the width into its columns
// with the same helpers Column Settings uses. A column with no `width` shares the rest.
const columns = ref<ListColumn[]>([
	{ fieldname: "lead_name", label: "Name", width: "12rem" },
	{ fieldname: "status", label: "Status", width: "8rem" },
	{ fieldname: "organization", label: "Organization" },
	{ fieldname: "annual_revenue", label: "Annual revenue", align: "right" },
]);

function resize({ fieldname, width }: ColumnResize) {
	columns.value = applyColumnWidth(columns.value, fieldname, width);
}

function reset({ fieldname }: { fieldname: string }) {
	columns.value = clearColumnWidth(columns.value, fieldname);
}
</script>

<template>
	<div class="flex h-80 w-full flex-col">
		<List
			:columns="columns"
			:rows="leads"
			class="px-2"
			@column-resize="resize"
			@column-reset="reset"
		/>
		<dl class="mt-3 grid grid-cols-[auto_1fr] gap-x-3 text-sm text-ink-gray-5">
			<template v-for="column in columns" :key="column.fieldname">
				<dt>{{ column.label }}</dt>
				<dd class="tabular-nums">{{ column.width ?? "share" }}</dd>
			</template>
		</dl>
	</div>
</template>
