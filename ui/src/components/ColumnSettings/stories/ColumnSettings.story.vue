<!--
  Isolated ColumnSettings demo — exercises the control on its own against a live
  doctype, showing the controlled `Column[]` `v-model` and the frappe-ui wire
  columns a host serializes from it. The doctype picker keys the demo body so it
  (and its `useDoctypeMeta`) reconstructs per doctype — the same remount pattern
  the Shell story uses, since `useDoctypeMeta` is taken by value. Story chrome
  uses frappe-ui components per the workspace convention.
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

		<ColumnSettingsDemo :key="doctype" :doctype="doctype" :hideLabel="hideLabel" />
	</div>
</template>

<script setup lang="ts">
import { ref } from "vue";
import { Select, Switch } from "frappe-ui";
import ColumnSettingsDemo from "./ColumnSettingsDemo.vue";

const doctypeOptions = ["CRM Lead", "CRM Deal", "CRM Task", "ToDo"];
const doctype = ref("CRM Lead");
const hideLabel = ref(false);
</script>
