<template>
	<SelectRow
		:label="__('Link')"
		:model-value="link_fieldname"
		:options="link_field_options"
		:placeholder="__('Select a link field')"
		@update:model-value="set_link_fieldname"
	/>
	<SelectRow
		v-if="link_fieldname"
		:label="__('Field')"
		:model-value="link_target_fieldname"
		:options="link_target_options"
		:placeholder="__('Select a field')"
		@update:model-value="set_link_target"
	/>
	<SizeRow
		v-if="linked_is_image"
		:label="__('Size')"
		:model-value="selected_field.width"
		@update:model-value="(v) => (selected_field.width = v)"
	/>
</template>

<script setup>
import { computed } from "vue";
import SelectRow from "./SelectRow.vue";
import SizeRow from "./SizeRow.vue";
import { useDoctypeFields } from "../../composables/useDoctypeFields";
import { value_field_opts } from "../../utils";
import { useSelectedField } from "./useSelectedField";

const { store, selected_field } = useSelectedField();

const link_fieldname = computed(() => (selected_field.value?.link_path || "").split(".")[0] || "");
const link_target_fieldname = computed(
	() => (selected_field.value?.link_path || "").split(".")[1] || ""
);
const link_field_options = computed(() =>
	(store.meta.value?.fields || [])
		.filter((f) => f.fieldtype === "Link" && f.options)
		.map((f) => ({ label: `${f.label || f.fieldname} (${f.options})`, value: f.fieldname }))
);
const link_target_fields = useDoctypeFields(
	computed(
		() =>
			(store.meta.value?.fields || []).find(
				(f) => f.fieldname === link_fieldname.value && f.fieldtype === "Link"
			)?.options
	)
);
const link_target_options = computed(() => value_field_opts(link_target_fields.value));
const linked_is_image = computed(
	() =>
		link_target_fields.value.find((f) => f.fieldname === link_target_fieldname.value)
			?.fieldtype === "Attach Image"
);

function set_link_fieldname(fieldname) {
	selected_field.value.link_path = fieldname ? fieldname + "." : "";
}
function set_link_target(fieldname) {
	selected_field.value.link_path = `${link_fieldname.value}.${fieldname}`;
	const target = link_target_fields.value.find((f) => f.fieldname === fieldname);
	if (target) selected_field.value.label = target.label || fieldname;
}
</script>
