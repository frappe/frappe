<template>
	<div class="field" :class="{ 'field-inline': inline }">
		<div v-if="df.label && df.show_label !== 'hide'" class="label">{{ df.label }}</div>
		<div class="value" :class="{ 'text-muted': !value }">{{ value || placeholder }}</div>
	</div>
</template>

<script setup>
import { computed, inject, ref, watchEffect } from "vue";

const props = defineProps(["df"]);
const store = inject("$store");

let inline = computed(() => (props.df.show_label || "inline") === "inline");
let value = ref("");
let placeholder = computed(() => props.df.link_path || __("No linked field set"));

const cache = {};
let pending_key = null;

watchEffect(() => {
	value.value = "";
	const path = props.df.link_path;
	const preview_doc = store.preview_doc.value;
	if (!path || !path.includes(".")) return;
	const [link_fieldname, target_fieldname] = path.split(".");
	const link_df = (store.meta.value?.fields || []).find(
		(f) => f.fieldname === link_fieldname && f.fieldtype === "Link"
	);
	if (!link_df?.options) return;
	const name = preview_doc?.[link_fieldname];
	if (!name) return;
	const key = `${link_df.options}:${name}:${target_fieldname}`;
	if (key in cache) {
		value.value = cache[key];
		return;
	}
	pending_key = key;
	frappe.db.get_value(link_df.options, name, target_fieldname).then((r) => {
		cache[key] = r?.message?.[target_fieldname] ?? "";
		if (pending_key === key) value.value = cache[key];
	});
});
</script>
