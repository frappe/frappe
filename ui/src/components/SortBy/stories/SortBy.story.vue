<!--
  Isolated SortBy demo — exercises the control on its own against a live doctype,
  showing the controlled `Sort[]` `v-model` and the `order_by` string a host would
  serialize from it. Story chrome uses frappe-ui components per the workspace
  convention.
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

		<div class="flex">
			<SortBy :key="doctype" v-model="sorts" :doctype="doctype" :hideLabel="hideLabel" />
		</div>

		<div class="flex flex-col gap-1 text-xs text-ink-gray-6">
			<div>Sort[] = {{ sorts }}</div>
			<div>order_by = "{{ orderBy }}"</div>
		</div>
	</div>
</template>

<script setup lang="ts">
import { computed, ref } from "vue";
import { Select, Switch } from "frappe-ui";
import { SortBy } from "../index";
import { serializeOrderBy } from "../orderBy";
import type { Sort } from "../types";

const doctypeOptions = ["CRM Lead", "CRM Deal", "CRM Task", "ToDo"];
const doctype = ref("CRM Lead");
const hideLabel = ref(false);
const sorts = ref<Sort[]>([]);

const orderBy = computed(() => serializeOrderBy(sorts.value));
</script>
