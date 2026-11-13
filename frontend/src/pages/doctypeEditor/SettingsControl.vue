<!-- The control of one catalogue row, by its `control`. Each change goes through the view, so it
     joins the header's Save and the one undo stack. -->
<template>
	<Switch
		v-if="row.control === 'switch'"
		size="sm"
		:model-value="Boolean(Number(view.value(prop)))"
		@update:model-value="view.set({ [prop]: $event ? 1 : 0 })"
	/>
	<TextInput
		v-else-if="row.control === 'number'"
		class="w-20"
		type="number"
		min="0"
		:model-value="Number(view.value(prop)) || 0"
		@change="view.set({ [prop]: Math.max(0, Math.trunc(Number(($event.target as HTMLInputElement).value)) || 0) })"
	/>
	<Combobox
		v-else-if="row.control === 'field'"
		class="w-[200px]"
		:model-value="String(view.value(prop) || NONE)"
		:options="[{ label: prop === 'title_field' ? __('None, the ID') : __('None'), value: NONE }, ...fieldChoices]"
		@update:model-value="view.set({ [prop]: $event && $event !== NONE ? String($event) : '' })"
	/>
	<SettingsFieldList v-else-if="row.control === 'fields'" :row="row" />
	<div v-else-if="row.control === 'sort'" class="flex items-center gap-2">
		<Select
			class="w-[140px]"
			:model-value="String(view.value('sort_field') || 'creation')"
			:options="sortOptions"
			@update:model-value="view.set({ sort_field: $event })"
		/>
		<TabButtons
			:options="ORDERS"
			:model-value="String(view.value('sort_order') || 'DESC')"
			@update:model-value="view.set({ sort_order: $event })"
		/>
	</div>
	<Select
		v-else-if="row.control === 'view'"
		class="w-[140px]"
		:model-value="String(view.value(prop) || 'List')"
		:options="VIEWS"
		@update:model-value="view.set({ [prop]: $event === 'List' ? '' : $event })"
	/>
	<RadioGroup
		v-else-if="row.control === 'kind'"
		padded
		class="-mx-1.5 flex flex-col gap-0.5"
		:model-value="view.kind"
		@update:model-value="view.set(kindProperties($event as DoctypeKind))"
	>
		<Radio v-for="kind in KINDS" :key="kind.value" :value="kind.value" :label="__(kind.label)" :description="__(kind.description)" />
	</RadioGroup>
</template>

<script setup lang="ts">
import { computed, inject } from "vue";
import { Combobox, Radio, RadioGroup, Select, Switch, TabButtons, TextInput } from "frappe-ui";
import { __ } from "@/i18n";
import SettingsFieldList from "./SettingsFieldList.vue";
import { KINDS, kindProperties, type DoctypeKind, type SettingRow } from "./settingsRows";
import { SettingsViewKey } from "./settingsView";

const props = defineProps<{ row: SettingRow }>();
const view = inject(SettingsViewKey)!;

const NONE = "__none";
const ORDERS = [
	{ label: __("Ascending"), value: "ASC" },
	{ label: __("Descending"), value: "DESC" },
];
const VIEWS = ["List", "Report", "Image", "Kanban", "Calendar", "Gantt"].map((value) => ({ label: __(value), value }));

const prop = computed(() => props.row.props[0]);
const fieldOptions = computed(() => view.fieldOptions(props.row.fieldtypes ?? []));
// A field the app set that this row's types leave out (ToDo's title is a Text Editor) still shows its label.
const fieldChoices = computed(() => {
	const current = String(view.value(prop.value) || "");
	if (!current || fieldOptions.value.some((option) => option.value === current)) return fieldOptions.value;
	return [...fieldOptions.value, { label: view.label(current), value: current }];
});
const sortOptions = computed(() => [
	{ label: __("Created on"), value: "creation" },
	{ label: __("Last updated"), value: "modified" },
	...fieldOptions.value,
]);
</script>
