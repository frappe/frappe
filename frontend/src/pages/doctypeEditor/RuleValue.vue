<!-- A builder row's value: the builder's own control for the field's type, or a field of this record
     (`eval:doc.company`). The `(x)` button at its end switches between the two. -->
<template>
	<div class="flex min-w-0 items-center gap-1">
		<div class="min-w-0 flex-1">
			<Combobox
				v-if="named !== null"
				class="w-full"
				:options="options"
				:model-value="modelValue"
				:placeholder="__('Pick a field')"
				data-rule-value-field
				@update:model-value="update(String($event ?? ''))"
			>
				<template #prefix>
					<span
						class="lucide-variable size-4 shrink-0 text-ink-gray-5"
						aria-hidden="true"
					/>
				</template>
			</Combobox>
			<ConditionValueControl
				v-else-if="field && !readonly"
				class="w-full"
				:field="field"
				:operator="operator"
				:model-value="modelValue"
				@update:model-value="update"
			/>
			<TextInput
				v-else
				class="w-full"
				readonly
				:model-value="listOf(modelValue).join(', ')"
			/>
		</div>
		<Tooltip v-if="switchable" :text="switchLabel">
			<Button
				variant="ghost"
				icon="lucide-variable"
				:label="switchLabel"
				:class="named !== null && '!bg-surface-gray-3 !text-ink-gray-8'"
				data-rule-value-switch
				@click="toggle"
			/>
		</Tooltip>
	</div>
</template>

<script setup lang="ts">
import { computed } from "vue";
import { Button, Combobox, TextInput, Tooltip } from "frappe-ui";
import {
	ConditionValueControl,
	fieldReference,
	referencedField,
	type ConditionField,
	type ConditionOperator,
	type ConditionValue,
} from "@framework/ui/ConditionBuilder";
import { __ } from "@/i18n";
import { listOf } from "./ruleWords";

const props = defineProps<{
	field: ConditionField | undefined;
	operator: ConditionOperator;
	modelValue: ConditionValue;
	readonly: boolean;
	update: (value: ConditionValue) => void;
	/** The fields of this record a value may name. */
	referable: ConditionField[];
	/** A condition's field is itself one of `referable`, and never compares with itself. */
	sameRecord?: boolean;
}>();

const COMPARES: ConditionOperator[] = ["equals", "not equals", "<", ">", "<=", ">="];

const named = computed(() => referencedField(props.modelValue));
const switchable = computed(
	() =>
		!props.readonly &&
		props.field?.fieldtype !== "Check" &&
		props.field?.fieldname !== "docstatus" &&
		COMPARES.includes(props.operator)
);
const switchLabel = computed(() =>
	named.value !== null ? __("Use a fixed value") : __("Use a field of this record")
);

// A Link compares with a Link to the same DocType first.
const options = computed(() => {
	const usable = props.referable.filter(
		(one) => !(props.sameRecord && one.fieldname === props.field?.fieldname)
	);
	const alike = (one: ConditionField) =>
		one.fieldtype === props.field?.fieldtype && one.options === props.field?.options;
	const option = (one: ConditionField) => ({
		label: one.label,
		value: fieldReference(one.fieldname),
	});
	const first = usable.filter(alike).map(option);
	const rest = usable.filter((one) => !alike(one)).map(option);
	if (!first.length) return rest;
	return [
		{ group: __("Same kind"), options: first },
		{ group: __("Other fields"), options: rest },
	];
});

function toggle() {
	if (named.value !== null) return props.update("");
	const first = options.value[0];
	const value = first && "options" in first ? first.options[0]?.value : first?.value;
	props.update(value ?? "");
}
</script>
