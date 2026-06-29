<!--
  The meta-bound body of the isolated ColumnSettings story, keyed by doctype so
  `useDoctypeMeta` (taken by value) reconstructs on a switch. Seeds the columns
  from the doctype's `in_list_view` defaults once Meta resolves, so add / remove /
  reorder / edit have real columns to act on, and prints the serialized wire
  columns a host would render the table from.
-->
<template>
	<div class="flex flex-col gap-4">
		<div class="flex">
			<ColumnSettings v-model="columns" :doctype="doctype" :hideLabel="hideLabel" />
		</div>

		<div class="flex flex-col gap-1 text-xs text-ink-gray-6">
			<div>Column[] = {{ columns }}</div>
			<div>wire columns = {{ wireColumns }}</div>
		</div>
	</div>
</template>

<script setup lang="ts">
import { computed, ref, watch } from "vue";
import { useDoctypeMeta } from "../../../composables/useDoctypeMeta";
import { ColumnSettings } from "../index";
import { serializeColumns } from "../columns";
import { getDefaultColumns } from "../getDefaultColumns";
import type { Column } from "../types";

const props = withDefaults(defineProps<{ doctype: string; hideLabel?: boolean }>(), {
	hideLabel: false,
});

const { meta } = useDoctypeMeta(props.doctype);
const columns = ref<Column[]>([]);

// Seed the shown columns from the doctype's `in_list_view` defaults once Meta
// resolves (it may already be cached → fires immediately).
watch(
	meta,
	(value) => {
		if (value) columns.value = getDefaultColumns(value.fields ?? []);
	},
	{ immediate: true }
);

const wireColumns = computed(() => serializeColumns(columns.value, meta.value?.fields ?? []));
</script>
