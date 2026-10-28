<template>
	<div class="value" :class="{ 'text-muted': !df.text }" :style="style">
		{{ text || __("Empty text") }}
	</div>
</template>

<script setup>
import { computed, inject, ref, watchEffect } from "vue";
import { linked_target } from "../../composables/linkedValues";
import { text_field_paths } from "../../utils";

const props = defineProps(["df", "style"]);
const store = inject("$store");

const paths = computed(() => text_field_paths(props.df.text, store.meta.value));

const linked = ref({});
watchEffect(() => {
	const doc = store.preview_doc.value;
	for (const path of paths.value) {
		if (!path.includes(".")) continue;
		const target = linked_target({ link_path: path }, store.meta.value, doc);
		if (!target || target.key in linked.value) continue;
		linked.value[target.key] = "";
		frappe.db
			.get_value(target.doctype, target.name, target.fieldname)
			.then((r) => (linked.value[target.key] = r?.message?.[target.fieldname] ?? ""));
	}
});

const text = computed(() => {
	const doc = store.preview_doc.value;
	return (props.df.text || "").replace(/\{([\w.]+)\}/g, (token, path) => {
		if (!paths.value.includes(path)) return token;
		if (!doc) return token;
		let value = store.preview_values.value?.[path] ?? doc[path] ?? "";
		if (path.includes(".")) {
			const target = linked_target({ link_path: path }, store.meta.value, doc);
			value = target ? linked.value[target.key] ?? "" : "";
		}
		return frappe.utils.html2text(String(value));
	});
});
</script>
