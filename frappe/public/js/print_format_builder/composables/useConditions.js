import { computed, ref, watch } from "vue";
import { layout_nodes } from "../layout";

export function useConditions(layout, preview_doc) {
	const results = ref({});
	const conditions = computed(() => {
		const out = new Set();
		for (const node of layout_nodes(layout.value)) {
			const expr = (node.visible_if || "").trim();
			if (expr) out.add(expr);
		}
		return [...out];
	});
	let seq = 0;
	const check = frappe.utils.debounce(() => {
		const doc = preview_doc.value;
		const mine = ++seq;
		if (!doc?.name || !conditions.value.length) return (results.value = {});
		frappe
			.call("frappe.utils.print_format_generator.check_conditions", {
				doctype: doc.doctype,
				name: doc.name,
				conditions: conditions.value,
			})
			.then((r) => mine === seq && (results.value = r.message || {}));
	}, 400);
	watch([() => conditions.value.join("\n"), () => preview_doc.value?.name], check, {
		immediate: true,
	});

	const condition_state = (expr) => results.value[(expr || "").trim()] || {};
	const is_visible = (expr) => !(expr || "").trim() || condition_state(expr).visible !== false;
	return { condition_state, is_visible };
}
