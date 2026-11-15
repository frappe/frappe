<script setup>
import { computed, ref, watch } from "vue";
import { Button, Dropdown } from "frappe-ui";
import { NumberCard } from "frappe-ui/charts";
import { useWidget } from "@framework/ui/widget";
import {
	format_doctype_number,
	load_card,
	load_trend,
	open_card,
} from "../../page/workspace_view/tiles/number_card.js";

const { widget, config, data, loading, error, filters, setFilters, refresh } = useWidget();

const frappe = window.frappe;
const __ = window.__;

const COMPARED_TO = {
	Daily: __("vs yesterday"),
	Weekly: __("vs last week"),
	Monthly: __("vs last month"),
	Quarterly: __("vs last 3 months"),
	Yearly: __("vs last year"),
};

const interval = computed(
	() => filters.value.stats_time_interval || config.value.stats_time_interval || "Daily"
);
const is_doctype = computed(() => (config.value.type || "Document Type") === "Document Type");

// the card as Number Card's own helpers take it, with its filters as full rows
const filter_rows = computed(() => {
	const rows = filters.value.filters || config.value.filters || [];
	if (!Array.isArray(rows)) return rows;
	return rows.map((row) => (row.length === 3 ? [config.value.document_type, ...row] : row));
});
const card = computed(() => ({
	...config.value,
	name: widget.value.name,
	type: config.value.type || "Document Type",
	stats_time_interval: interval.value,
	filters_json: JSON.stringify(filter_rows.value),
}));

const value = ref(null);
const delta = ref(null);
const trend = ref(null);
const failed = ref(false);
let latest = 0;

// A Document Type card comes worked out from the server; a Report or Custom one loads here.
async function draw() {
	const run = ++latest;
	failed.value = false;
	try {
		const result = is_doctype.value
			? {
					value: await format_doctype_number(card.value, data.value?.value),
					delta: data.value?.delta,
			  }
			: await load_card(card.value);
		if (run !== latest) return;
		value.value = result.value;
		delta.value = typeof result.delta === "number" ? result.delta : null;
	} catch (e) {
		if (run === latest) failed.value = true;
		return;
	}
	const points = await load_trend({ card: card.value, filters: filter_rows.value }).catch(
		() => null
	);
	if (run === latest) trend.value = points;
}

watch(data, draw, { immediate: true });

const can_pick_interval = computed(
	() => config.value.show_percentage_stats && !widget.value.hide_filter
);
const intervals = computed(() =>
	Object.entries(COMPARED_TO).map(([option, label]) => ({
		label,
		onClick: () => setFilters({ stats_time_interval: option }),
	}))
);

const menu = computed(() => [
	{ label: __("Refresh"), icon: "lucide-refresh-cw", onClick: refresh },
	{ label: __("Open"), icon: "lucide-arrow-up-right", onClick: open },
]);

function open() {
	open_card({ card: card.value, filters: filter_rows.value, data: data.value });
}
</script>

<template>
	<NumberCard
		class="group h-full cursor-pointer hover:border-outline-gray-2 dark:border-outline-gray-2 dark:bg-transparent dark:hover:border-outline-gray-3"
		:title="widget.label"
		:value="value"
		:color="config.color || undefined"
		:delta="delta"
		delta-suffix="%"
		:delta-format="(number) => frappe.utils.shorten_number(number)"
		:delta-caption="delta === null ? undefined : COMPARED_TO[interval]"
		:sparkline="trend ? { data: trend, color: config.color || undefined } : undefined"
		:loading="loading || (value === null && !failed && !error)"
		:error="failed || error ? __('Could not load') : null"
		@click="open"
	>
		<template v-if="can_pick_interval" #caption>
			<Dropdown :options="intervals">
				<template #trigger>
					<button
						type="button"
						class="flex items-center gap-0.5 text-p-sm text-ink-gray-5 hover:text-ink-gray-7"
						@click.stop
					>
						{{ COMPARED_TO[interval] }}
						<span class="lucide-chevron-down size-3" aria-hidden="true" />
					</button>
				</template>
			</Dropdown>
		</template>
		<template #actions>
			<div class="opacity-0 transition-opacity group-hover:opacity-100" @click.stop>
				<Dropdown align="end" :options="menu">
					<template #trigger>
						<Button
							variant="ghost"
							size="sm"
							icon="lucide-more-horizontal"
							:label="__('Number card actions')"
						/>
					</template>
				</Dropdown>
			</div>
		</template>
	</NumberCard>
</template>
