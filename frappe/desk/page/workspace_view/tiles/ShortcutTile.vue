<script setup>
import { computed, onMounted, ref, watch } from "vue";
import Shortcut from "../../../widget_type/shortcut/shortcut.vue";
import { provide_widget_state, short_filters } from "../widget.js";

// An old label-keyed shortcut, drawn by the Shortcut widget's renderer. Its count loads here.
const props = defineProps({
	widget: { type: Object, required: true },
});

const frappe = window.frappe;
const count = ref(null);
const loading = ref(false);
const error = ref(null);

const widget = computed(() => {
	const row = props.widget;
	const filters = frappe.utils.process_filter_expression(row.stats_filter);
	return {
		label: row.label,
		config: { ...row, stats_filter: short_filters(filters, row.link_to) },
	};
});

const data = computed(() => ({
	count: count.value,
	is_query_report: props.widget.is_query_report,
	ref_doctype: props.widget.ref_doctype,
	report_ref_doctype: props.widget.report_ref_doctype,
}));

provide_widget_state({ widget, data, loading, error });

const counts = computed(() => {
	const { type, doc_view, link_to } = props.widget;
	return (
		type === "DocType" &&
		link_to &&
		doc_view !== "New" &&
		!frappe.boot.single_types.includes(link_to)
	);
});

let request = 0;
async function load_count() {
	const current = ++request;
	count.value = null;
	error.value = null;
	if (!counts.value) return;
	loading.value = true;
	try {
		const result = await frappe.db.count(props.widget.link_to, {
			filters: widget.value.config.stats_filter,
		});
		if (current === request) count.value = result;
	} catch (e) {
		if (current === request) error.value = e;
	} finally {
		if (current === request) loading.value = false;
	}
}

onMounted(load_count);
// the editor changes these live
watch(() => [props.widget.link_to, props.widget.doc_view, props.widget.stats_filter], load_count);
</script>

<template>
	<Shortcut />
</template>
