import { computed, inject } from "vue";

export function useSelectedField() {
	const store = inject("$store");
	const selected_field = computed(() => store.selected_field.value);
	const preview_doc = computed(() => store.preview_doc.value);

	return { store, selected_field, preview_doc };
}
