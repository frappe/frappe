import { ref, watch } from "vue";

// Load a doctype's meta fields whenever the (reactive) doctype name changes —
// the shared shape behind every "pick a field of the linked/child doctype" row.
export function useDoctypeFields(doctype_ref) {
	let fields = ref([]);
	watch(
		doctype_ref,
		(doctype) => {
			fields.value = [];
			if (!doctype) return;
			frappe.model.with_doctype(doctype, () => {
				fields.value = frappe.get_meta(doctype).fields;
			});
		},
		{ immediate: true }
	);
	return fields;
}
