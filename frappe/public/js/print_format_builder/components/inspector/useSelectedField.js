import { computed, inject } from "vue";

export function useSelectedField() {
	const store = inject("$store");
	const selected_field = computed(() => store.selected_field.value);
	const preview_doc = computed(() => store.preview_doc.value);

	function remove_field() {
		if (selected_field.value) {
			selected_field.value.remove = true;
			store.selected_field.value = null;
		}
	}

	return { store, selected_field, preview_doc, remove_field };
}
