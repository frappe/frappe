<!-- Used as Text, Small Text & Long Text Control -->
<script setup>
import { useStore } from "../../store";
import { useSlots, ref, computed, watch } from "vue";
import { computedAsync } from "@vueuse/core";

let store = useStore();
const props = defineProps(["df", "value", "modelValue"]);
let emit = defineEmits(["update:modelValue"]);
let slots = useSlots();

let height = computed(() => {
	if (props.df.fieldtype == "Small Text") {
		return "150px";
	}
	return "300px";
});

let doctype = ref("");
let fieldname = ref("");
let doctypes = ref("");

let doctype_df = computed(() => {
	doctypes.value = store
		.get_updated_fields()
		.filter(df => df.fieldtype == "Link")
		.filter(df => df.options && df.fieldname != store.form.selected_field.fieldname)
		.sort((a, b) => a.options.localeCompare(b.options))
		.map(df => ({
			label: `${df.options} (${df.fieldname})`,
			value: df.fieldname,
			doctype_name: df.options
		}));

	let options = [{ label: __("Select DocType"), value: "" }, ...doctypes.value];
	return { fieldtype: "Select", label: __("Fetch Form"), options };
});

let field_df = computedAsync(async () => {
	let options = [{ label: __("Select Field"), value: "" }];
	let df = { fieldtype: "Select", label: __("Fetch Form"), options };
	if (!doctype.value) return df;
	let doctype_name = doctypes.value?.find(df => df.value == doctype.value).doctype_name;
	if (!doctype_name) return df;

	if (props.value.split(".")[0] != doctype.value) {
		fieldname.value = "";
	}

	await frappe.model.with_doctype(doctype_name);

	let fields = frappe.meta
		.get_docfields(doctype_name, null, {
			fieldtype: ["not in", frappe.model.no_value_type]
		})
		.sort((a, b) => {
			if (a.label && b.label) {
				return a.label.localeCompare(b.label);
			}
		})
		.map(df => ({
			label: `${df.label || __("No Label")} (${df.fieldtype})`,
			value: df.fieldname
		}));

	df.options = df.options.concat(fields);
	return df;
}, {});

watch(
	() => props.value,
	value => {
		if (props.df.fieldname == "fetch_from") {
			[doctype.value, fieldname.value] = value?.split(".") || ["", ""];
		}
	},
	{ immediate: true }
);

watch([() => doctype.value, () => fieldname.value], ([doctype_value, fieldname_value]) => {
	let [doctype_name, field_name] = props.value?.split(".") || ["", ""];
	if (
		props.df.fieldname == "fetch_from" &&
		(doctype_value != doctype_name || fieldname_value != field_name)
	) {
		emit("update:modelValue", `${doctype_value}.${fieldname_value}`);
	}
});
</script>

<template>
	<div v-if="df.fieldname == 'fetch_from'">
		<SelectControl :df="doctype_df" :value="doctype" v-model="doctype" />
		<SelectControl
			v-if="doctype"
			:df="field_df"
			:value="fieldname"
			v-model="fieldname"
			:no_label="true"
		/>
	</div>
	<div v-else class="control" :class="{ editable: slots.label }">
		<!-- label -->
		<div v-if="slots.label" class="field-controls">
			<slot name="label" />
			<slot name="actions" />
		</div>
		<div v-else class="label">{{ df.label }}</div>

		<!-- textarea input -->
		<textarea
			v-if="slots.label"
			:style="{ height: height, maxHeight: df.max_height ?? '' }"
			class="form-control"
			type="text"
			readonly
		/>
		<textarea
			v-else
			:style="{ height: height, maxHeight: df.max_height ?? '' }"
			class="form-control"
			type="text"
			:value="value"
			:disabled="store.read_only || df.read_only"
			@input="event => $emit('update:modelValue', event.target.value)"
		/>

		<!-- description -->
		<div v-if="df.description" class="mt-2 description" v-html="df.description"></div>
	</div>
</template>
