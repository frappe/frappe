import { computed, inject } from "vue";

export function useSelectedField() {
	const store = inject("$store");
	const selected_field = computed(() => store.selected_field.value);
	const preview_doc = computed(() => store.preview_doc.value);

	function set_field_prop(key, value) {
		if (value) selected_field.value[key] = value;
		else delete selected_field.value[key];
	}

	return { store, selected_field, preview_doc, set_field_prop };
}
