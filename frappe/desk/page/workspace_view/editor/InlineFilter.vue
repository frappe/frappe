<script setup>
import { computed, ref, watch } from "vue";
import { Button, Combobox, Select } from "frappe-ui";
import { useDoctypeMeta } from "@framework/ui";
import {
	VALUE_CONTROLS,
	carryOver,
	conditionFor,
	defaultValueFor,
	getFilterableFields,
	getOperators,
	parseFilters,
	serializeFilters,
	valueControl,
} from "@framework/ui/Filter";

// A filter list edited in place, one condition stacked under the next so it fits the panel.
// Desk stores [doctype, field, operator, value] rows, all of them joined by AND.
const props = defineProps({
	doctype: { type: String, required: true },
	filters: { type: Array, default: null },
});

const emit = defineEmits(["change"]);
const __ = window.__;

const { meta } = useDoctypeMeta(props.doctype);
const fields = computed(() => getFilterableFields(meta.value?.fields ?? [], props.doctype));

// kept here, since a condition without a value yet is not written back
const conditions = ref(null);

// standard fields are listed before the meta arrives, so wait for the meta itself
watch(
	[meta, fields],
	([meta, fields]) => {
		if (conditions.value || !meta) return;
		const checks = new Set(
			fields.filter((f) => f.fieldtype === "Check").map((f) => f.fieldname)
		);
		const rows = (props.filters || []).map(([, field, operator, value]) => [
			field,
			operator,
			checks.has(field) && value !== "" ? Boolean(Number(value)) : value,
		]);
		conditions.value = parseFilters(fields, rows);
	},
	{ immediate: true }
);

function commit(next) {
	conditions.value = next;
	emit(
		"change",
		serializeFilters(next).map(([field, operator, value]) => [
			props.doctype,
			field,
			operator,
			value,
		])
	);
}

function field_of(option) {
	const fieldname = typeof option === "string" ? option : option?.value;
	return fields.value.find((f) => f.fieldname === fieldname) ?? null;
}

function add(option) {
	const field = field_of(option);
	if (field) commit([...conditions.value, conditionFor(field)]);
}

function set_field(option, index) {
	const field = field_of(option);
	if (!field) return;
	commit(conditions.value.map((c, i) => (i === index ? carryOver(c, field) : c)));
}

function set_operator(operator, index) {
	commit(
		conditions.value.map((c, i) =>
			i === index ? { ...c, operator, value: defaultValueFor(c.field, operator) } : c
		)
	);
}

function set_value(value, index) {
	commit(conditions.value.map((c, i) => (i === index ? { ...c, value } : c)));
}

function remove(index) {
	commit(conditions.value.filter((_, i) => i !== index));
}
</script>

<template>
	<div v-if="conditions" class="flex flex-col gap-2">
		<div
			v-for="(condition, index) in conditions"
			:key="index"
			class="flex flex-col gap-1.5 rounded-4 border border-outline-gray-1 p-2"
		>
			<div class="flex items-center gap-1">
				<Combobox
					class="min-w-0 flex-1"
					trigger="button"
					variant="subtle"
					:model-value="condition.fieldname"
					:options="fields"
					:placeholder="__('Select field')"
					@update:selected-option="(option) => set_field(option, index)"
				/>
				<Button
					size="sm"
					variant="ghost"
					icon="lucide-trash-2"
					:label="__('Remove condition')"
					@click="remove(index)"
				/>
			</div>
			<Select
				:model-value="condition.operator"
				:options="getOperators(condition.field?.fieldtype ?? '', condition.fieldname)"
				@update:model-value="(operator) => set_operator(operator, index)"
			/>
			<component
				:is="VALUE_CONTROLS[valueControl(condition).control]"
				v-bind="valueControl(condition).props"
				class="w-full"
				:model-value="condition.value"
				@update:model-value="(value) => set_value(value, index)"
			/>
		</div>
		<Combobox :options="fields" :model-value="null" @update:selected-option="add">
			<template #trigger>
				<Button class="self-start" icon-left="lucide-plus" :label="__('Add condition')" />
			</template>
		</Combobox>
	</div>
</template>
