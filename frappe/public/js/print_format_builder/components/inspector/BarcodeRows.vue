<template>
	<template v-if="selected_field.custom">
		<DropdownRow
			:label="__('Value from')"
			:model-value="selected_field.barcode_field || ''"
			:options="field_options"
			@update:model-value="(v) => set_field_prop('barcode_field', v)"
		/>
		<TextRow
			v-if="!selected_field.barcode_field"
			:label="__('Value')"
			:placeholder="__('Static value')"
			:model-value="selected_field.barcode_value"
			@update:model-value="(v) => (selected_field.barcode_value = v)"
		/>
		<DropdownRow
			:label="__('Format')"
			:model-value="selected_field.barcode_format || 'CODE128'"
			:options="formats"
			@update:model-value="(v) => (selected_field.barcode_format = v)"
		/>
	</template>
	<SizeRow
		:label="__('Size')"
		:min="40"
		:max="500"
		:fallback="selected_field.barcode_format === 'QR' ? 130 : 200"
		:model-value="selected_field.width"
		@update:model-value="(v) => (selected_field.width = v)"
	/>
	<ToggleRow
		v-if="selected_field.custom && selected_field.barcode_format !== 'QR'"
		:label="__('Value text')"
		:model-value="selected_field.show_text !== false"
		@update:model-value="(v) => set_field_prop('show_text', v, true)"
	/>
</template>

<script setup>
import { computed } from "vue";
import DropdownRow from "./DropdownRow.vue";
import TextRow from "./TextRow.vue";
import SizeRow from "./SizeRow.vue";
import ToggleRow from "./ToggleRow.vue";
import { useSelectedField } from "./useSelectedField";

const { store, selected_field, set_field_prop } = useSelectedField();

const formats = ["CODE128", "CODE39", "QR"].map((f) => ({ value: f, label: f }));
const field_options = computed(() => [
	{ label: __("Static value"), value: "" },
	{ label: __("ID (name)"), value: "name" },
	...(store.meta.value?.fields || [])
		.filter((f) => !frappe.model.no_value_type.includes(f.fieldtype))
		.map((f) => ({ label: f.label || f.fieldname, value: f.fieldname })),
]);
</script>
