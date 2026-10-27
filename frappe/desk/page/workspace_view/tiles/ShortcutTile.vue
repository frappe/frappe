<script setup>
import { computed, inject, onMounted, ref, watch } from "vue";
import { Tooltip } from "frappe-ui";
import { describe_link_filters } from "../../../../public/js/frappe/form/controls/link_filter_description.js";
import { badge_theme } from "./badge_theme.js";

const props = defineProps({
	widget: { type: Object, required: true },
});

const frappe = window.frappe;
const __ = window.__;
const { format_number, strip_html } = window;
const size = inject("tile_size", ref("M"));
const rtl = frappe.utils.is_rtl();
const count = ref(null);
const failed = ref(false);

const TYPE_ICONS = {
	Report: "lucide-chart-no-axes-column",
	Page: "lucide-app-window",
	Dashboard: "lucide-layout-dashboard",
	URL: "lucide-globe",
};

const VIEW_ICONS = {
	New: "lucide-plus",
	Kanban: "lucide-square-kanban",
	Calendar: "lucide-calendar",
	Tree: "lucide-list-tree",
	"Report Builder": "lucide-sheet",
	Image: "lucide-image",
	Dashboard: "lucide-layout-dashboard",
};

const DOTS = {
	green: "bg-surface-green-7",
	red: "bg-surface-red-7",
	amber: "bg-surface-amber-7",
	blue: "bg-surface-blue-7",
	violet: "bg-surface-violet-7",
};

const single = computed(() => frappe.boot.single_types.includes(props.widget.link_to));

const icon = computed(() => {
	const { type, doc_view } = props.widget;
	if (type !== "DocType") return TYPE_ICONS[type] || "lucide-list";
	if (single.value) return "lucide-settings-2";
	return VIEW_ICONS[doc_view] || "lucide-list";
});

const label = computed(() => strip_html(props.widget.label));
const filters = computed(() => frappe.utils.process_filter_expression(props.widget.stats_filter));
// old shortcuts store filters as an object, e.g. { "status": "Open" }
const filtered = computed(() => Object.keys(filters.value || {}).length > 0);

const counts = computed(() => {
	const { type, doc_view, link_to } = props.widget;
	return type === "DocType" && link_to && doc_view !== "New" && !single.value;
});

const filter_lines = ref([]);
let described = false;
let request = 0;

async function load_count() {
	const current = ++request;
	count.value = null;
	failed.value = false;
	filter_lines.value = [];
	described = false;
	if (!counts.value) return;
	try {
		const result = await frappe.db.count(props.widget.link_to, {
			filters: filters.value || [],
		});
		if (current === request) count.value = result;
	} catch {
		if (current === request) failed.value = true;
	}
}

onMounted(load_count);
// the editor changes these live
watch(() => [props.widget.link_to, props.widget.doc_view, props.widget.stats_filter], load_count);

const with_format = (number) =>
	props.widget.format ? __(props.widget.format).replace(/{}/g, number) : number;

// A small tile shows only the number, shortened past 10,000. The tooltip has the rest.
const count_text = computed(() => {
	if (count.value === null) return null;
	if (size.value !== "S") return with_format(format_number(count.value, null, 0));
	if (count.value < 10000) return format_number(count.value, null, 0);
	const compact = { notation: "compact", maximumFractionDigits: 1 };
	return new Intl.NumberFormat(frappe.boot.lang, compact).format(count.value);
});

const name = computed(() => {
	if (count.value === null) return label.value;
	const full = with_format(format_number(count.value, null, 0));
	return filtered.value
		? __("{0}, {1} matching filter", [label.value, full])
		: `${label.value}, ${full}`;
});

const dot = computed(() => (count.value ? DOTS[badge_theme(props.widget.color)] : null));

// described on first hover, since field labels need the doctype's meta
async function describe_filters() {
	if (described || !filtered.value) return;
	described = true;
	await frappe.model.with_doctype(props.widget.link_to);
	filter_lines.value = await describe_link_filters(props.widget.link_to, filters.value);
}

const title = computed(() => [name.value, ...filter_lines.value].join("\n"));

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
		class="group flex h-11 w-full items-center gap-2.5 rounded-4 border border-outline-gray-1 bg-surface-elevation-2 px-2.5 text-start transition-colors hover:bg-surface-gray-1 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-outline-gray-3 active:bg-surface-gray-2 dark:border-outline-gray-2"
		:title="title"
		:aria-label="name"
		@mouseenter="describe_filters"
		@focus="describe_filters"
		@click="open"
	>
		<span
			class="grid size-6 shrink-0 place-items-center rounded-2 bg-surface-gray-2 text-ink-gray-6"
		>
			<span :class="[icon, 'size-3.5']" aria-hidden="true" />
		</span>
		<span class="min-w-0 flex-1 truncate text-base font-medium text-ink-gray-8">
			{{ label }}
		</span>
		<span class="flex shrink-0 items-center gap-1.5">
			<span
				v-if="counts && count === null && !failed"
				class="h-3 w-8 animate-pulse rounded-1 bg-surface-gray-3"
			/>
			<Tooltip v-else-if="failed" :text="__('Could not load the count')">
				<span class="text-sm text-ink-gray-6">–</span>
			</Tooltip>
			<template v-else-if="count_text !== null">
				<span
					v-if="filtered"
					class="lucide-list-filter size-3 text-ink-gray-5"
					aria-hidden="true"
				/>
				<span v-if="dot" class="size-1.5 rounded-full" :class="dot" />
				<span class="text-sm tabular-nums text-ink-gray-6">{{ count_text }}</span>
			</template>
			<span
				v-else-if="widget.type === 'URL'"
				:class="[
					rtl ? 'lucide-arrow-up-left' : 'lucide-arrow-up-right',
					'size-4 text-ink-gray-5',
				]"
				aria-hidden="true"
			/>
			<span
				v-else
				:class="[
					rtl ? 'lucide-chevron-left' : 'lucide-chevron-right',
					'size-4 text-ink-gray-5 opacity-0 transition-opacity group-hover:opacity-100 group-focus-visible:opacity-100',
				]"
				aria-hidden="true"
			/>
		</span>
	</button>
</template>
