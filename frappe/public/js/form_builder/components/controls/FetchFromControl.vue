<!-- Used as Fetch From Control -->
<script setup>
import { useStore } from "../../store";
import { load_doctype_model } from "../../utils";
import { ref, computed, watch } from "vue";
import { computedAsync } from "@vueuse/core";

let store = useStore();
const props = defineProps(["df", "value", "read_only", "modelValue"]);
let emit = defineEmits(["update:modelValue"]);

let doctype = ref("");
let fieldname = ref("");
let doctypes = ref("");

let doctype_df = computed(() => {
	doctypes.value = store
		.get_updated_fields()
		.filter((df) => df.fieldtype == "Link")
		.filter((df) => df.options && df.fieldname != store.form.selected_field.fieldname)
		.sort((a, b) => a.options.localeCompare(b.options))
		.map((df) => ({
			label: `${df.options} (${df.fieldname})`,
			value: df.fieldname,
			doctype_name: df.options,
		}));

	let options = [{ label: __("Select DocType"), value: "" }, ...doctypes.value];
	return { fieldtype: "Select", label: __("Fetch From"), options };
});

let field_df = computedAsync(async () => {
	let options = [{ label: __("Select Field"), value: "" }];
	let df = { fieldtype: "Select", label: __("Fetch From"), options };
	if (!doctype.value) return df;
	let doctype_name = doctypes.value?.find((df) => df.value == doctype.value).doctype_name;
	if (!doctype_name) return df;

	if (props.value.split(".")[0] != doctype.value) {
		fieldname.value = "";
	}

	await load_doctype_model(doctype_name);

	let fields = frappe.meta
		.get_docfields(doctype_name, null, {
			fieldtype: ["not in", frappe.model.no_value_type],
		})
		.sort((a, b) => {
			if (a.label && b.label) {
				return a.label.localeCompare(b.label);
			}
		})
		.map((df) => ({
			label: `${df.label || __("No Label")} (${df.fieldtype})`,
			value: df.fieldname,
		}));

	df.options = df.options.concat(fields);
	return df;
}, {});

watch(
	() => props.value,
	(value) => {
		if (value) [doctype.value, fieldname.value] = value.split(".") || ["", ""];
	},
	{ immediate: true }
);

watch([() => doctype.value, () => fieldname.value], ([doctype_value, fieldname_value]) => {
	let [doctype_name, field_name] = props.value?.split(".") || ["", ""];
	if (doctype_value != doctype_name || fieldname_value != field_name) {
		let fetch_expression = "";
		if (doctype_value && fieldname_value) {
			fetch_expression = `${doctype_value}.${fieldname_value}`;
		}
		emit("update:modelValue", fetch_expression);
	}
});
</script>

<template>
	<div>
		<SelectControl
			:df="doctype_df"
			:value="doctype"
			:read_only="read_only"
			v-model="doctype"
		/>
		<SelectControl
			v-if="doctype"
			:df="field_df"
			:read_only="read_only"
			:value="fieldname"
			v-model="fieldname"
			:no_label="true"
		/>
	</div>
</template>
