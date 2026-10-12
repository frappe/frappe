import { computed, inject } from "vue";
import { set_prop } from "../../utils";

export function useSelectedField() {
	const store = inject("$store");
	const selected_field = computed(() => store.selected_field.value);
	const selected_fields = computed(() => store.selected_fields.value);
	const preview_doc = computed(() => store.preview_doc.value);

	function set_field_prop(key, value, fallback) {
		set_prop(selected_field.value, key, value, fallback);
	}

	return { store, selected_field, selected_fields, preview_doc, set_field_prop };
}
