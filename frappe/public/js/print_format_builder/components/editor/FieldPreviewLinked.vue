<template>
	<div
		v-if="df.label && df.show_label !== 'hide'"
		class="label"
		:class="{ 'label--no-colon': df.hide_colon }"
	>
		{{ df.label }}
	</div>
	<div v-if="is_image && value" class="value">
		<img :style="{ maxWidth: '100%', width: df.width || '100%' }" :src="value" />
	</div>
	<div v-else class="value" :class="{ 'text-muted': !value }">{{ value || placeholder }}</div>
</template>

<script setup>
import { computed, inject, ref, watchEffect } from "vue";
import { useDoctypeFields } from "../../composables/useDoctypeFields";

const props = defineProps(["df"]);
const store = inject("$store");

let value = ref("");
let placeholder = computed(() => props.df.link_path || __("No linked field set"));

let link_options = computed(() => {
	const link_fieldname = (props.df.link_path || "").split(".")[0];
	return (store.meta.value?.fields || []).find(
		(f) => f.fieldname === link_fieldname && f.fieldtype === "Link"
	)?.options;
});
let target_fields = useDoctypeFields(link_options);
let is_image = computed(() => {
	const target = (props.df.link_path || "").split(".")[1];
	return target_fields.value.find((f) => f.fieldname === target)?.fieldtype === "Attach Image";
});

const cache = {};
let pending_key = null;

watchEffect(() => {
	value.value = "";
	pending_key = null;
	const path = props.df.link_path;
	const preview_doc = store.preview_doc.value;
	if (!path || !path.includes(".")) return;
	const [link_fieldname, target_fieldname] = path.split(".");
	if (!target_fieldname) return;
	const link_df = (store.meta.value?.fields || []).find(
		(f) => f.fieldname === link_fieldname && f.fieldtype === "Link"
	);
	if (!link_df?.options) return;
	const name = preview_doc?.[link_fieldname];
	if (!name) return;
	const key = `${link_df.options}:${name}:${target_fieldname}`;
	pending_key = key;
	cache[key] ??= frappe.db
		.get_value(link_df.options, name, target_fieldname)
		.then((r) => r?.message?.[target_fieldname] ?? "")
		.catch(() => {
			delete cache[key];
			return "";
		});
	cache[key].then((v) => {
		if (pending_key === key) value.value = v;
	});
});
</script>
