<!--
  Isolated QuickFilter demo. The strip and the Filter control bind the SAME `filters` ref,
  so a quick input and its matching condition stay in sync with no wiring.
-->
<template>
	<div class="flex flex-col gap-4 p-6">
		<div class="flex items-center gap-4">
			<div class="flex items-center gap-2">
				<span class="text-p-sm text-ink-gray-6">Doctype</span>
				<Select v-model="doctype" :options="doctypeOptions" class="w-56" />
			</div>
			<div v-if="quickFilter.canCustomize.value" class="flex items-center gap-2">
				<span class="text-p-sm text-ink-gray-6">Customize</span>
				<Switch v-model="quickFilter.customizing.value" />
			</div>
		</div>

		<div class="flex items-center gap-2">
			<QuickFilter
				class="flex-1"
				v-model:filters="filters.conditions.value"
				v-model:fields="quickFilter.fields.value"
				v-model:customizing="quickFilter.customizing.value"
				:doctype="doctype"
			/>
			<Filter v-model="filters.conditions.value" :doctype="doctype" />
		</div>

		<div class="flex flex-col gap-1 text-xs text-ink-gray-6">
			<div>FilterCondition[] = {{ filters.conditions.value }}</div>
			<div>filters = {{ filters.wire.value }}</div>
		</div>
	</div>
</template>

<script setup lang="ts">
import { computed, ref } from "vue";
import { Select, Switch } from "frappe-ui";
import { Filter } from "../../Filter";
import { useFilters } from "../../Filter/useFilters";
import { QuickFilter } from "../index";
import { useQuickFilter } from "../useQuickFilter";

const doctypeOptions = ["CRM Lead", "CRM Deal", "CRM Task", "ToDo"];
const doctype = ref("CRM Lead");

const filters = useFilters();

// Rebuilt per doctype to mirror a host's `:key="doctype"` remount — Meta is cached per
// doctype string, so reconstructing is cheap and resets the surfaced fields on switch.
const quickFilter = computed(() => useQuickFilter(doctype.value));
</script>
