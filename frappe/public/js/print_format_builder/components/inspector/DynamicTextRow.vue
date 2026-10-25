<template>
	<TemplateInput v-model="template" :fields="field_opts" />
</template>

<script setup>
import { computed, ref, watchEffect } from "vue";
import TemplateInput from "./TemplateInput.vue";
import { value_field_opts } from "../../utils";
import { useSelectedField } from "./useSelectedField";

const { store, selected_field } = useSelectedField();

const template = computed(() => (selected_field.value.template ||= []));

const linked_opts = ref([]);
watchEffect(async () => {
	const links = (store.meta.value?.fields || []).filter(
		(f) => f.fieldtype === "Link" && f.options
	);
	await Promise.all(links.map((f) => frappe.model.with_doctype(f.options)));
	linked_opts.value = links.flatMap((link) =>
		value_field_opts(frappe.get_meta(link.options)?.fields).map((o) => ({
			label: `${link.label || link.fieldname} › ${o.label}`,
			value: `${link.fieldname}.${o.value}`,
		}))
	);
});

const field_opts = computed(() => [
	...value_field_opts(store.meta.value?.fields),
	...linked_opts.value,
]);
</script>
