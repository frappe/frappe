<!--
  The built-in leaf's value control: the input `Filter` picks for the field's type
  and the operator. Exported so a host's `#condition-value` can wrap it, with a
  "compare with a field" switch say, and still edit a value the builder's way.
-->
<template>
	<component
		:is="VALUE_CONTROLS[control.control]"
		v-bind="control.props"
		:modelValue="controlValue"
		@update:modelValue="emit('update:modelValue', $event)"
	/>
</template>

<script setup lang="ts">
import { computed, provide } from "vue";
import type { Filter } from "../Filter/types";
import { valueControl } from "../Filter/valueControl";
import { VALUE_CONTROLS } from "../Filter/valueControlComponents";
import { CreateRecordKey, FieldActionsKey, RecordLinkKey } from "../Fields/types";
import type { ConditionField, ConditionOperator, ConditionValue } from "./types";

const props = defineProps<{
	field: ConditionField;
	operator: ConditionOperator;
	modelValue: ConditionValue;
}>();

const emit = defineEmits<{ "update:modelValue": [value: ConditionValue] }>();

// A condition's value input picks a record; it never creates or opens one.
provide(CreateRecordKey, null);
provide(RecordLinkKey, null);
provide(FieldActionsKey, null);

const control = computed(() =>
	valueControl({
		fieldname: props.field.fieldname,
		operator: props.operator,
		value: props.modelValue as Filter["value"],
		field: props.field,
	})
);

// Controls that take and emit `string[]`: both coerce a non-array to `[]`, so a
// stored comma string is dropped the moment the row is touched.
const ARRAY_CONTROLS = ["multiSelect", "multiLink"];

/** The field's own option list, where the fieldtype has a fixed one. Empty for
 *  a Link, whose values are not enumerable here. */
const knownOptions = computed<Set<string>>(() => {
	const options = props.field.options;
	if (control.value.control !== "multiSelect" || typeof options !== "string") {
		return new Set();
	}
	return new Set(
		options
			.split("\n")
			.map((option) => option.trim())
			.filter(Boolean)
	);
});

/**
 * Persisted as a comma string while the multi-value controls take arrays. A
 * whole string that is itself a known option wins over splitting, since a value
 * may contain a comma.
 */
const controlValue = computed<ConditionValue>(() => {
	const value = props.modelValue;
	if (!ARRAY_CONTROLS.includes(control.value.control)) return value;
	if (Array.isArray(value)) return value;
	if (typeof value !== "string" || value === "") return [];

	const known = knownOptions.value;
	if (known.has(value.trim())) return [value.trim()];

	const parts = value
		.split(",")
		.map((part) => part.trim())
		.filter(Boolean);

	// One unrecognised part means the comma was inside a value, not between two.
	if (known.size > 0 && parts.some((part) => !known.has(part))) {
		return [value.trim()];
	}
	return parts;
});
</script>
