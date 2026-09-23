import { ref } from "vue";

export function usePreviewDoc(print_format, print_format_name) {
	const preview_doc = ref(null);
	const preview_doc_name = ref(null);
	const preview_values = ref({});
	const preview_child_values = ref({});
	let preview_load_seq = 0;

	const preview_doc_ls_key = `pfb:preview_doc:${print_format_name}`;
	function persisted_preview_doc_name() {
		return localStorage.getItem(preview_doc_ls_key);
	}
	function load_preview_doc(name) {
		const seq = ++preview_load_seq;
		if (!name) {
			preview_doc.value = null;
			preview_doc_name.value = null;
			preview_values.value = {};
			preview_child_values.value = {};
			localStorage.removeItem(preview_doc_ls_key);
			return;
		}
		preview_doc_name.value = name;
		localStorage.setItem(preview_doc_ls_key, name);
		frappe.db.get_doc(print_format.value.doc_type, name).then((doc) => {
			if (seq !== preview_load_seq) return;
			preview_doc.value = doc;
		});
		frappe
			.call("frappe.utils.print_format_generator.get_formatted_field_values", {
				doctype: print_format.value.doc_type,
				name,
			})
			.then((r) => {
				if (seq !== preview_load_seq) return;
				preview_values.value = r.message?.values || {};
				preview_child_values.value = r.message?.child || {};
			});
	}

	return {
		preview_doc,
		preview_doc_name,
		preview_values,
		preview_child_values,
		load_preview_doc,
		persisted_preview_doc_name,
	};
}
