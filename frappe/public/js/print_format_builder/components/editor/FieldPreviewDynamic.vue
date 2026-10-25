<template>
	<div class="value" :class="{ 'text-muted': !text }" :style="style">
		{{ text || __("Empty text") }}
	</div>
</template>

<script setup>
import { computed, inject, ref, watchEffect } from "vue";
import { linked_target } from "../../composables/linkedValues";

const props = defineProps(["df", "style"]);
const store = inject("$store");

const linked = ref({});
watchEffect(() => {
	const doc = store.preview_doc.value;
	for (const token of props.df.template || []) {
		if (token.t !== "f" || !token.v.includes(".")) continue;
		const target = linked_target({ link_path: token.v }, store.meta.value, doc);
		if (!target || target.key in linked.value) continue;
		linked.value[target.key] = "";
		frappe.db
			.get_value(target.doctype, target.name, target.fieldname)
			.then((r) => (linked.value[target.key] = r?.message?.[target.fieldname] ?? ""));
	}
});

const text = computed(() => {
	const doc = store.preview_doc.value;
	return (props.df.template || [])
		.map((token) => {
			if (token.t !== "f") return token.v;
			if (!doc) return "[" + token.v + "]";
			if (token.v.includes(".")) {
				const target = linked_target({ link_path: token.v }, store.meta.value, doc);
				return target ? linked.value[target.key] ?? "" : "";
			}
			return store.preview_values.value?.[token.v] ?? doc[token.v] ?? "";
		})
		.join("")
		.trim();
});
</script>
