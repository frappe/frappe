<script setup>
import { computed, onMounted, ref } from "vue";
import { Badge } from "frappe-ui";

const props = defineProps({
	widget: { type: Object, required: true },
});

const frappe = window.frappe;
const __ = window.__;
const count = ref(null);

const BADGE_THEMES = {
	Grey: "gray",
	Green: "green",
	Red: "red",
	Orange: "amber",
	Pink: "violet",
	Yellow: "amber",
	Blue: "blue",
	Cyan: "blue",
};

const counts = computed(() => {
	const { type, doc_view, link_to } = props.widget;
	return (
		type === "DocType" &&
		link_to &&
		doc_view !== "New" &&
		!frappe.boot.single_types.includes(link_to)
	);
});

onMounted(async () => {
	if (!counts.value) return;
	const filters = frappe.utils.process_filter_expression(props.widget.stats_filter);
	count.value = await frappe.db.count(props.widget.link_to, { filters: filters || [] });
});

const label = computed(() => {
	if (count.value === null) return null;
	const format = props.widget.format;
	return format ? __(format).replace(/{}/g, count.value) : String(count.value);
});

const theme = computed(() =>
	props.widget.color && count.value ? BADGE_THEMES[props.widget.color] || "gray" : "gray"
);

function open(event) {
	const w = props.widget;
	if (w.type === "DocType" && w.doc_view === "New") {
		// no redirect after the record is made
		frappe.ui.form.make_quick_entry(w.link_to, () => {});
		return;
	}
	if (w.type === "URL") {
		window.open(w.url, "_blank");
		return;
	}

	const filters = frappe.utils.get_filter_from_json(w.stats_filter);
	if (w.type === "DocType" && filters) frappe.route_options = filters;
	if (event.ctrlKey || event.metaKey) frappe.open_in_new_tab = true;
	frappe.set_route(
		frappe.utils.generate_route({
			name: w.link_to,
			type: w.type,
			is_query_report: w.is_query_report,
			doctype: w.ref_doctype,
			doc_view: w.doc_view,
			kanban_board: w.kanban_board,
			report_ref_doctype: w.report_ref_doctype,
		})
	);
}
</script>

<template>
	<button
		type="button"
		class="flex h-full w-full items-center justify-between gap-2 rounded-6 border border-outline-gray-1 bg-surface-base px-4 text-left hover:border-outline-gray-2 focus-visible:outline focus-visible:outline-2 focus-visible:outline-outline-gray-3"
		@click="open"
	>
		<span class="truncate text-base font-medium text-ink-gray-8">{{ widget.label }}</span>
		<span class="flex shrink-0 items-center gap-2">
			<Badge v-if="label !== null" :label="label" :theme="theme" />
			<span class="lucide-arrow-up-right size-3 text-ink-gray-5" aria-hidden="true" />
		</span>
	</button>
</template>
