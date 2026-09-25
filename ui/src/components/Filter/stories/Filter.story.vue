<!--
  Isolated Filter demo — exercises the control on its own against a live doctype,
  showing the controlled `FilterCondition[]` `v-model` and the Frappe filters dict a
  host would serialize from it. Story chrome uses frappe-ui components per the
  workspace convention.
-->
<template>
	<div class="flex flex-col gap-4 p-6">
		<div class="flex items-center gap-2">
			<span class="text-p-sm text-ink-gray-6">Doctype</span>
			<Select v-model="doctype" :options="doctypeOptions" class="w-56" />
		</div>

		<div class="flex">
			<Filter :key="doctype" v-model="filters" :doctype="doctype" />
		</div>

		<div class="flex flex-col gap-1 text-xs text-ink-gray-6">
			<div>FilterCondition[] = {{ filters }}</div>
			<div>filters = {{ wireFilters }}</div>
		</div>
	</div>
</template>

<script setup lang="ts">
import { computed, ref } from "vue";
import { Select } from "frappe-ui";
import { Filter, serializeFilters } from "../index";
import type { FilterCondition } from "../index";

const doctypeOptions = ["CRM Lead", "CRM Deal", "CRM Task", "ToDo"];
const doctype = ref("CRM Lead");
const filters = ref<FilterCondition[]>([]);

const wireFilters = computed(() => serializeFilters(filters.value));
</script>
