<script setup>
import { computed, ref } from "vue";
import { Tooltip } from "frappe-ui";
import { openWidget, useWidget } from "@framework/ui/widget";
import { describe_link_filters } from "../../../public/js/frappe/form/controls/link_filter_description.js";
import { badge_theme } from "../../page/workspace_view/tiles/badge_theme.js";

const { widget, config, data, loading, error, size } = useWidget();

const frappe = window.frappe;
const __ = window.__;
const { format_number, strip_html } = window;
const rtl = frappe.utils.is_rtl();

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

const icon = computed(() => {
	const { type, doc_view, link_to } = config.value;
	if (type !== "DocType") return TYPE_ICONS[type] || "lucide-list";
	if (frappe.boot.single_types.includes(link_to)) return "lucide-settings-2";
	return VIEW_ICONS[doc_view] || "lucide-list";
});

const label = computed(() => strip_html(widget.value.label));
const filters = computed(() => config.value.stats_filter || []);
const filtered = computed(() => filters.value.length > 0);
const count = computed(() => data.value?.count ?? null);

const with_format = (number) =>
	config.value.format ? __(config.value.format).replace(/{}/g, number) : number;

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

const dot = computed(() => (count.value ? DOTS[badge_theme(config.value.color)] : null));

// described on first hover, since field labels need the doctype's meta
const filter_lines = ref([]);
let described = false;
async function describe_filters() {
	if (described || !filtered.value) return;
	described = true;
	await frappe.model.with_doctype(config.value.link_to);
	filter_lines.value = await describe_link_filters(config.value.link_to, filters.value);
}

const title = computed(() => [name.value, ...filter_lines.value].join("\n"));

function open(event) {
	openWidget({ ...config.value, ...data.value, filters: filters.value }, event);
}
</script>

<template>
	<button
		type="button"
		class="group flex h-11 w-full items-center gap-2.5 rounded-4 border border-outline-gray-1 bg-surface-elevation-2 px-2.5 text-start transition-colors hover:bg-surface-gray-1 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-outline-gray-3 active:bg-surface-gray-2 dark:border-outline-gray-2 dark:bg-transparent"
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
			<span v-if="loading" class="h-3 w-8 animate-pulse rounded-1 bg-surface-gray-3" />
			<Tooltip v-else-if="error" :text="__('Could not load the count')">
				<span class="text-sm text-ink-gray-6">–</span>
			</Tooltip>
			<template v-else-if="count_text !== null">
				<span
					v-if="filtered"
					class="lucide-list-filter size-3 text-ink-gray-5"
					aria-hidden="true"
				/>
				<span v-if="dot" class="size-1.5 rounded-full" :class="dot" />
				<span class="text-sm text-ink-gray-6">{{ count_text }}</span>
			</template>
			<span
				v-else-if="config.type === 'URL'"
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
