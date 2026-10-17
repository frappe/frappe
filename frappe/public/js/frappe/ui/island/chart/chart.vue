<script setup>
import { computed } from "vue";
import {
	AreaChart,
	BarChart,
	CalendarHeatmapChart,
	DonutChart,
	FunnelChart,
	HeatmapChart,
	LineChart,
	OTHERS_KEY,
	SankeyChart,
	ScatterChart,
} from "frappe-ui/charts";
import { useHost } from "@framework/ui/island";

import { format_keys, from_legacy_config, is_legacy_chart_config } from "./legacy_config.js";

const props = defineProps({
	config: { type: Object, required: true },
});

const __ = window.__;
const host = useHost();

const CHARTS = {
	bar: BarChart,
	line: LineChart,
	area: AreaChart,
	donut: DonutChart,
	funnel: FunnelChart,
	heatmap: HeatmapChart,
	"calendar-heatmap": CalendarHeatmapChart,
	sankey: SankeyChart,
	scatter: ScatterChart,
};

const parsed = computed(() => {
	try {
		const config = is_legacy_chart_config(props.config)
			? from_legacy_config(props.config, {
					center_label: __("Total"),
					on_unknown_key: warn_unknown_key,
			  })
			: { ...props.config, ...format_keys(props.config) };
		if (!CHARTS[config.type]) {
			throw new Error(__("Unknown chart type {0}", [config.type]));
		}
		return { config };
	} catch (e) {
		return { error: e.message };
	}
});

const chart = computed(() => CHARTS[parsed.value.config?.type] || BarChart);

const chart_props = computed(() => {
	const { config, error } = parsed.value;
	if (error) return { data: [], x: "", y: "", error };

	// desk's own keys: what the chart is, how its values read, how tall it is
	const { type, fieldtype, options, precision, currency, height, ...rest } = config;
	const df = { fieldtype, options, precision };
	const format = value_format(df, config);

	if (["bar", "line", "area"].includes(type)) {
		const series = series_dfs(rest, df);
		// an axis reads as its first series does
		const axis_df = (columns) => series[[columns].flat()[0]]?.df || df;
		return {
			...rest,
			seriesConfig: Object.fromEntries(
				Object.entries(series).map(([key, { df, style }]) => [
					key,
					{ ...style, format: value_format(df, config) },
				])
			),
			yAxis: { ...rest.yAxis, format: axis_format(axis_df(rest.y), config) },
			y2Axis: { ...rest.y2Axis, format: axis_format(axis_df(rest.y2), config) },
		};
	}
	if (type === "scatter") {
		return {
			...rest,
			format,
			xAxis: { ...rest.xAxis, format: axis_format({}, config) },
			yAxis: { ...rest.yAxis, format: axis_format(df, config) },
		};
	}
	return { ...rest, format };
});

function warn_unknown_key(key) {
	if (!host.developer_mode || warned_keys.has(key)) return;
	warned_keys.add(key);
	console.warn(`frappe.ui.chart: "${key}" is a frappe-charts option the new charts do not draw`);
}

const height = computed(() => {
	const px = parsed.value.config?.height;
	return px ? { height: `${px}px` } : null;
});

/** Every value prints as desk prints a field of its type. A number with no type reads as a Float. */
function value_format(df, doc) {
	if (!host.format) return undefined;
	const field = { ...df, fieldtype: df.fieldtype || "Float" };
	return (value) => host.format(value, field, doc);
}

/** An axis tick, shortened. `df` keeps what the shortening loses, such as a currency's symbol. */
function axis_format(df, doc) {
	if (!host.format_axis_number) return undefined;
	return (value) => host.format_axis_number(value, df, doc);
}

/**
 * Each series' df and its style. A series names its own fieldtype when its unit differs from
 * the chart's, and its own precision when it reads finer or coarser.
 */
function series_dfs(config, df) {
	const split = config.splitBy
		? [...config.data.map((row) => row[config.splitBy]), OTHERS_KEY]
		: [];
	const keys = [config.y, config.y2, split].flat().filter((key) => key != null && key !== "");
	const series = { ...config.seriesConfig };
	for (const key of keys) series[key] ||= {};
	return Object.fromEntries(
		Object.entries(series).map(([key, { fieldtype, options, precision, ...style }]) => {
			const own = fieldtype ? { fieldtype, options } : df;
			return [key, { style, df: { ...own, precision: precision ?? own.precision } }];
		})
	);
}
</script>

<script>
// once per page, not once per chart
const warned_keys = new Set();
</script>

<template>
	<div class="h-full w-full" :style="height">
		<component :is="chart" v-bind="chart_props" />
	</div>
</template>
