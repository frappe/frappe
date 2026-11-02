<template>
	<div class="pfb-static-text">
		<textarea
			ref="input"
			class="form-control form-control-sm pfb-static-text-input"
			:placeholder="__('Type text, / for a field')"
			rows="4"
			:value="selected_field.text || ''"
			@input="on_input"
			@keydown="on_key"
			@blur="slash = null"
		></textarea>
		<ul v-if="slash" class="dropdown-menu show pfb-tpl-menu">
			<li v-for="(f, k) in slash_matches" :key="f.value">
				<a
					class="dropdown-item"
					:class="{ highlighted: k === slash.highlight }"
					:title="f.label"
					href="#"
					@mousedown.prevent="pick(f)"
				>
					{{ f.label }}
				</a>
			</li>
			<li v-if="!slash_matches.length" class="dropdown-item text-muted">
				{{ __("No matching field") }}
			</li>
		</ul>
	</div>
</template>

<script setup>
import { computed, nextTick, ref, watchEffect } from "vue";
import { value_field_opts } from "../../utils";
import { useSelectedField } from "./useSelectedField";

const { store, selected_field } = useSelectedField();
const input = ref(null);
const slash = ref(null);

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

const slash_matches = computed(() => {
	if (!slash.value) return [];
	const q = slash.value.query.toLowerCase();
	return field_opts.value.filter(
		(f) => !q || f.label.toLowerCase().includes(q) || f.value.toLowerCase().includes(q)
	);
});

function on_input(e) {
	const value = e.target.value;
	const caret = e.target.selectionStart;
	selected_field.value.text = value;
	if (slash.value && value[slash.value.start] === "/" && caret > slash.value.start) {
		slash.value.query = value.slice(slash.value.start + 1, caret);
		slash.value.highlight = 0;
	} else if (value[caret - 1] === "/") {
		slash.value = { start: caret - 1, query: "", highlight: 0 };
	} else {
		slash.value = null;
	}
}

function pick(f) {
	const { start, query } = slash.value;
	const text = selected_field.value.text || "";
	const token = `{${f.value}}`;
	selected_field.value.text =
		text.slice(0, start) + token + text.slice(start + 1 + query.length);
	slash.value = null;
	nextTick(() => {
		const caret = start + token.length;
		input.value.focus();
		input.value.setSelectionRange(caret, caret);
	});
}

function on_key(e) {
	if (!slash.value) return;
	const n = slash_matches.value.length;
	if (e.key === "ArrowDown" && n) {
		e.preventDefault();
		slash.value.highlight = (slash.value.highlight + 1) % n;
	} else if (e.key === "ArrowUp" && n) {
		e.preventDefault();
		slash.value.highlight = (slash.value.highlight - 1 + n) % n;
	} else if (e.key === "Enter" && n) {
		e.preventDefault();
		pick(slash_matches.value[slash.value.highlight]);
	} else if (e.key === "Escape") {
		slash.value = null;
	}
}
</script>
