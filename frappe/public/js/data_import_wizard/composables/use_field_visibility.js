import { computed, ref, onMounted, onBeforeUnmount, watch } from "vue";

/** Evaluate meta depends_on / hidden the same way as layout.refresh_dependency. */
export function use_field_visible(frm, fieldname, dependency_getters = []) {
	const tick = ref(0);
	const stop_handles = [];

	const bump = () => {
		tick.value += 1;
	};

	const normalized_getters = Array.isArray(dependency_getters)
		? dependency_getters
		: [dependency_getters];

	for (const getter of normalized_getters) {
		if (typeof getter !== "function") continue;
		stop_handles.push(
			watch(
				getter,
				() => {
					bump();
				},
				{ immediate: false }
			)
		);
	}

	onMounted(() => {
		$(frm.wrapper).on("form-refresh.data_import_vue refresh-fields.data_import_vue", bump);
	});

	onBeforeUnmount(() => {
		$(frm.wrapper).off("form-refresh.data_import_vue refresh-fields.data_import_vue", bump);
		for (const stop of stop_handles) {
			stop?.();
		}
	});

	return computed(() => {
		tick.value;
		const field = frm.fields_dict?.[fieldname];
		const df = field?.df || frappe.meta.get_docfield(frm.doctype, fieldname, frm.doc.name);
		if (!df || cint(df.hidden)) {
			return false;
		}
		if (df.depends_on) {
			return !!frm.layout?.evaluate_depends_on_value(df.depends_on);
		}
		return !cint(df.hidden_due_to_dependency);
	});
}
