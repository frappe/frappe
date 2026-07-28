<!--
  The `in` / `not in` value input for a Link field: a frappe-ui MultiSelect whose
  options are searched live from the link's target doctype (`search_link`, the same
  endpoint `Link.vue` uses), so the user picks real records instead of typing a
  comma string of names. Its `v-model` is the condition's value — a `string[]` of
  the selected record names.

  Records already selected but absent from the current search results are merged
  back into the options (from a remembered cache) so their chips stay labelled as
  the query narrows the list.
-->
<template>
	<MultiSelect
		:modelValue="selected"
		:options="options"
		:loading="resource.loading && !resource.data"
		:placeholder="placeholder ?? `Search ${(field.options ?? '').toLowerCase()}`"
		variant="subtle"
		emptyText="No results found"
		@update:modelValue="(v) => emit('update:modelValue', v)"
		@update:query="onQuery"
		@update:open="onOpen"
	/>
</template>

<script setup lang="ts">
import { computed, ref, watch } from "vue";
import { MultiSelect, createResource, frappeRequest, debounce } from "frappe-ui";
import type { FilterField } from "./types";

const props = defineProps<{
	field: FilterField;
	modelValue: string[];
	placeholder?: string;
}>();

const emit = defineEmits<{ "update:modelValue": [value: string[]] }>();

interface LinkOption {
	label: string;
	value: string;
	description?: string;
}

const selected = computed<string[]>(() =>
	Array.isArray(props.modelValue) ? props.modelValue : []
);

// Every option we've ever seen, so a selected-but-filtered-out record keeps its
// label after the query narrows the result set.
const known = ref(new Map<string, LinkOption>());

const resource = createResource({
	url: "frappe.desk.search.search_link",
	params: { doctype: props.field.options ?? "", txt: "", filters: {} },
	method: "POST",
	resourceFetcher: frappeRequest,
	transform: (data: { value: string; label?: string; description?: string }[]): LinkOption[] =>
		data.map((doc) => ({
			label: doc.label || doc.value,
			value: doc.value,
			description: doc.description,
		})),
});

watch(
	() => resource.data as LinkOption[] | undefined,
	(data) => {
		for (const o of data ?? []) known.value.set(o.value, o);
	}
);

const options = computed<LinkOption[]>(() => {
	const byId = new Map<string, LinkOption>();
	for (const o of (resource.data as LinkOption[]) ?? []) byId.set(o.value, o);
	// Merge selected-but-absent values so their chips stay resolvable.
	for (const v of selected.value) {
		if (!byId.has(v)) byId.set(v, known.value.get(v) ?? { label: v, value: v });
	}
	return Array.from(byId.values());
});

function load(txt = "") {
	if (!props.field.options) return;
	resource.update({ params: { doctype: props.field.options, txt, filters: {} } });
	resource.reload();
}

const onQuery = debounce((q: string) => load(q || ""), 300);

function onOpen(isOpen: boolean) {
	if (isOpen && !resource.data) load("");
}
</script>
