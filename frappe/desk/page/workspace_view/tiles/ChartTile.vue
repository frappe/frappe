<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from "vue";
import { Button, DateRangePicker, Dropdown } from "frappe-ui";
import { ChartCard, ChartContainer } from "frappe-ui/charts";
import DeskFilter from "./DeskFilter.vue";
import { text_of } from "./number_card.js";
import {
	DATE_RANGE,
	TIMESPANS,
	TIME_INTERVALS,
	chart_config,
	export_csv,
	fetch_data,
	has_data,
	initial_filters,
	load_chart,
	save_settings,
} from "./chart.js";

const props = defineProps({
	widget: { type: Object, required: true },
});

const frappe = window.frappe;
const __ = window.__;

const chart = ref(null);
const settings = ref({ ...(props.widget.chart_settings || {}) });
const filters = ref(null);
const state = ref({ loading: true });
const target = ref(null);
let handle = null;

const doc = computed(() => chart.value?.doc);

async function load() {
	state.value = { loading: true };
	try {
		chart.value = await load_chart(props.widget.chart_name);
		if (chart.value.island) return mount(chart.value.island.name, chart.value.island.props);
		filters.value = await initial_filters(doc.value, settings.value);
		await draw();
	} catch (e) {
		state.value = { error: e.message || __("This chart couldn't load") };
	}
}

async function draw() {
	state.value = { ...state.value, loading: true };
	try {
		const { data, result, summary } = await fetch_data(
			chart.value,
			filters.value,
			settings.value
		);
		refresh_last_synced();
		if (!has_data(doc.value, data)) {
			state.value = { empty: true };
			return;
		}
		state.value = { data, summary: summary || [], loading: true };
		// the plot fills what the summary row leaves of the tile
		await nextTick();
		const config = await chart_config(
			chart.value,
			data,
			result,
			settings.value,
			target.value.clientHeight
		);
		mount("frappe.chart", { config });
	} catch (e) {
		state.value = { error: e.message || __("This chart couldn't load") };
	}
}

// The chart itself is desk's chart island, loaded on first use, so it shares the one conversion
// from the frappe-charts shape.
function mount(island, island_props) {
	requestAnimationFrame(() => {
		if (!target.value) return;
		if (handle && handle.island === island) {
			handle.update(island_props);
			state.value = { ...state.value, loading: false };
			return;
		}
		handle?.unmount();
		handle = frappe.ui.mount_island(island, target.value, island_props);
		handle.island = island;
		handle.ready.then(() => (state.value = { ...state.value, loading: false }));
	});
}

onMounted(load);
onBeforeUnmount(() => handle?.unmount());

function refresh_last_synced() {
	frappe.db.get_value("Dashboard Chart", doc.value.name, "last_synced_on").then((r) => {
		doc.value.last_synced_on = r.message?.last_synced_on;
	});
}

function save(changes) {
	Object.assign(settings.value, changes);
	save_settings(doc.value, settings.value);
	draw();
}

function reset() {
	save_settings(doc.value, {}, 1);
	settings.value = {};
	filters.value = null;
	load();
}

const last_synced = computed(() =>
	doc.value?.last_synced_on
		? __("Last synced {0}", [frappe.datetime.prettyDate(doc.value.last_synced_on)])
		: ""
);

const is_doctype_chart = computed(
	() => doc.value && !["Report", "Custom"].includes(doc.value.chart_type)
);
const is_heatmap = computed(() => doc.value?.type === "Heatmap");

const interval_options = computed(() =>
	TIME_INTERVALS.map((value) => ({
		label: __(value),
		onClick: () => save({ time_interval: value }),
	}))
);
const timespan_options = computed(() => [
	{
		label: __(DATE_RANGE),
		onClick: () => (settings.value = { ...settings.value, timespan: DATE_RANGE }),
	},
	...TIMESPANS.map((value) => ({
		label: __(value),
		onClick: () => save({ timespan: value, from_date: null, to_date: null }),
	})),
]);
const year_options = computed(() =>
	frappe.dashboard_utils
		.get_years_since_creation(frappe.boot.user.creation)
		.map((year) => ({ label: year, onClick: () => save({ heatmap_year: year }) }))
);

const date_range = computed({
	get: () => [settings.value.from_date, settings.value.to_date].filter(Boolean).join(","),
	set: (value) => {
		const [from_date, to_date] = (value || "").split(",");
		if (from_date && to_date) save({ timespan: DATE_RANGE, from_date, to_date });
	},
});

function set_filters(rows) {
	filters.value = rows;
	save({ filters: rows });
}

function open_filter_dialog() {
	frappe.dashboard_utils.get_filters_for_chart_type(doc.value).then((fields) => {
		fields = fields?.length
			? fields.filter((df) => df.fieldname).map((df) => ({ ...df, ...df.dashboard_config }))
			: [{ fieldtype: "HTML", options: __("No Filters Set") }];
		const dialog = new frappe.ui.Dialog({
			title: __("Set Filters for {0}", [__(doc.value.chart_name)]),
			fields,
			primary_action_label: __("Set"),
			primary_action: (values) => {
				dialog.hide();
				filters.value = values;
				save({ filters: values });
			},
		});
		dialog.show();
		if (doc.value.chart_type === "Report") {
			// report filters read their values from the current query report
			frappe.query_report = new frappe.views.QueryReport({ filters: dialog.fields_list });
			frappe.query_reports[doc.value.report_name]?.onload?.(frappe.query_report);
		}
		dialog.set_values(filters.value);
	});
}

const menu = computed(() => {
	if (!doc.value) return [];
	const items = [
		{ label: __("Refresh"), icon: "lucide-refresh-cw", onClick: load },
		{
			label: __("Edit"),
			icon: "lucide-pen",
			onClick: () => frappe.set_route("Form", "Dashboard Chart", doc.value.name),
		},
	];
	if (chart.value.island) return items;
	items.push(
		{ label: __("Reset Chart"), icon: "lucide-rotate-ccw", onClick: reset },
		{
			label: __("Export"),
			icon: "lucide-download",
			onClick: () => export_csv(doc.value, state.value.data),
		}
	);
	if (doc.value.document_type) {
		items.push({
			label: __("{0} List", [__(doc.value.document_type)]),
			icon: "lucide-list",
			onClick: () => frappe.set_route("List", doc.value.document_type),
		});
	} else if (doc.value.chart_type === "Report") {
		items.push({
			label: __("{0} Report", [__(doc.value.report_name)]),
			icon: "lucide-file-text",
			onClick: () => frappe.set_route("query-report", doc.value.report_name, filters.value),
		});
	}
	return items;
});

function summary_value(item) {
	return text_of(
		frappe.format(
			item.value,
			{ fieldtype: item.datatype, options: item.currency },
			{
				only_value: true,
			}
		)
	);
}

watch(
	() => props.widget.chart_name,
	() => load()
);
</script>

<template>
	<ChartCard class="h-full">
		<ChartContainer
			:title="widget.label"
			:subtitle="last_synced"
			:loading="state.loading"
			:error="state.error"
			:empty="state.empty"
		>
			<template #actions>
				<div v-if="doc && !chart.island" class="flex items-center gap-1">
					<template v-if="doc.timeseries && is_heatmap">
						<Dropdown :options="year_options">
							<Button
								size="sm"
								:label="String(settings.heatmap_year || doc.heatmap_year)"
							/>
						</Dropdown>
					</template>
					<template v-else-if="doc.timeseries">
						<DateRangePicker
							v-if="settings.timespan === DATE_RANGE"
							v-model="date_range"
							class="w-48"
							:placeholder="__('Date Range')"
						/>
						<Dropdown :options="timespan_options">
							<Button size="sm" :label="__(settings.timespan || doc.timespan)" />
						</Dropdown>
						<Dropdown :options="interval_options">
							<Button
								size="sm"
								icon-left="lucide-calendar"
								:label="__(settings.time_interval || doc.time_interval)"
							/>
						</Dropdown>
					</template>
					<DeskFilter
						v-if="is_doctype_chart && doc.document_type"
						:doctype="doc.document_type"
						:filters="filters"
						@change="set_filters"
					/>
					<Button
						v-else
						size="sm"
						icon="lucide-list-filter"
						:label="__('Filter')"
						@click="open_filter_dialog"
					/>
				</div>
				<Dropdown v-if="doc" align="end" :options="menu">
					<Button
						size="sm"
						variant="ghost"
						icon="lucide-more-horizontal"
						:label="__('Chart actions')"
					/>
				</Dropdown>
			</template>
			<template #empty>
				<span class="text-p-sm text-ink-gray-5">
					{{
						doc?.empty_state_message ? __(doc.empty_state_message) : __("No data yet")
					}}
				</span>
			</template>
			<template #error="{ error }">
				<span class="max-w-sm text-p-sm text-ink-gray-5">{{ error }}</span>
			</template>
			<div class="flex h-full flex-col gap-2">
				<div
					v-if="state.summary?.length"
					class="grid grid-cols-[repeat(auto-fit,minmax(8rem,1fr))] gap-x-4 gap-y-3"
				>
					<div v-for="item in state.summary" :key="item.label" class="flex flex-col">
						<span class="text-sm text-ink-gray-5">{{ item.label }}</span>
						<span class="text-base font-medium text-ink-gray-8">
							{{ summary_value(item) }}
						</span>
					</div>
				</div>
				<div ref="target" class="min-h-0 w-full flex-1" />
			</div>
		</ChartContainer>
	</ChartCard>
</template>
