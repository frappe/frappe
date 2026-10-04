<template>
	<div v-if="selected_field.html" class="pfb-html-preview" v-html="preview"></div>
	<div v-else class="pfb-insp-hint text-muted">{{ __("No HTML content yet.") }}</div>
	<button class="es-button" data-size="xs" @click="edit">
		<span v-html="frappe.utils.icon('pencil', 'xs')"></span>
		{{ __("Edit HTML") }}
	</button>
</template>

<script setup>
import { computed } from "vue";
import { strip_unsafe_html } from "../../utils";
import { open_html_editor } from "../../composables/useHtmlEditorDialog";
import { useSelectedField } from "./useSelectedField";

const { store, selected_field } = useSelectedField();
const preview = computed(() => strip_unsafe_html(selected_field.value?.html || ""));

function edit() {
	open_html_editor({
		title: __("Edit HTML"),
		initial_html: selected_field.value?.html || "",
		doctype: store.meta.value?.name,
		docname: store.preview_doc_name.value,
		on_save: (html) => (selected_field.value.html = html),
	});
}
</script>
