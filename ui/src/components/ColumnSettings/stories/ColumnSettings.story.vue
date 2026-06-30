<!--
  Isolated ColumnSettings demo — exercises the control on its own against a live
  doctype, showing the controlled `Column[]` `v-model` and the frappe-ui wire
  columns a host serializes from it. Switching doctype re-resolves meta (via a
  cheap cache-backed `useDoctypeMeta` call in a `watchEffect`, since the composable
  is taken by value) and reseeds the columns from the doctype's `in_list_view`
  defaults. Story chrome uses frappe-ui components per the workspace convention.
-->
<template>
	<div class="flex flex-col gap-4 p-6">
		<div class="flex items-center gap-4">
			<div class="flex items-center gap-2">
				<span class="text-p-sm text-ink-gray-6">Doctype</span>
				<Select v-model="doctype" :options="doctypeOptions" class="w-56" />
			</div>
			<div class="flex items-center gap-2">
				<span class="text-p-sm text-ink-gray-6">Hide label</span>
				<Switch v-model="hideLabel" />
			</div>
		</div>

		<div class="flex flex-col gap-4">
			<div class="flex">
				<ColumnSettings v-model="columns" :doctype="doctype" :hideLabel="hideLabel" />
			</div>

			<div class="flex flex-col gap-1 text-xs text-ink-gray-6">
				<div>Column[] = {{ columns }}</div>
				<div>wire columns = {{ wireColumns }}</div>
			</div>
		</div>
	</div>
</template>

<script setup lang="ts">
import { computed, ref, watch, watchEffect } from "vue";
import { Select, Switch } from "frappe-ui";
import { useDoctypeMeta } from "../../../composables/useDoctypeMeta";
import type { DoctypeMeta } from "../../../composables/useDoctypeMeta";
import { ColumnSettings } from "../index";
import { serializeColumns } from "../columns";
import { getDefaultColumns } from "../getDefaultColumns";
import type { Column } from "../types";

const doctypeOptions = ["CRM Lead", "CRM Deal", "CRM Task", "ToDo"];
const doctype = ref("CRM Lead");
const hideLabel = ref(false);

// `useDoctypeMeta` is taken by value, so re-resolve it whenever the picker
// changes. The call is cache-backed (one fetch per doctype, shared), and reading
// the returned `meta` ref inside the effect keeps us tracking its async resolve.
const meta = ref<DoctypeMeta | null>(null);
watchEffect(() => {
	meta.value = useDoctypeMeta(doctype.value).meta.value;
});

const columns = ref<Column[]>([]);

// Seed the shown columns from the doctype's `in_list_view` defaults once Meta
// resolves (it may already be cached → fires immediately), and on every switch.
watch(
	meta,
	(value) => {
		if (value) columns.value = getDefaultColumns(value.fields ?? [], value.title_field);
	},
	{ immediate: true }
);

const wireColumns = computed(() => serializeColumns(columns.value, meta.value?.fields ?? []));
</script>
