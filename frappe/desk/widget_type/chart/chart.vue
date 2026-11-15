<script setup>
import { computed } from "vue";
import { useWidget } from "@framework/ui/widget";
import ChartTile from "../../page/workspace_view/tiles/ChartTile.vue";

const { widget, config, data } = useWidget();

// the widget's own filters, timespan and interval, under the reader's saved ones
const tile = computed(() => {
	const { chart, filters, timespan, time_interval } = config.value;
	const own = Object.fromEntries(
		Object.entries({ filters, timespan, time_interval }).filter(([, value]) => value)
	);
	return {
		label: widget.value.label,
		chart_name: chart,
		chart_settings: { ...own, ...data.value?.chart_settings },
	};
});
</script>

<template>
	<ChartTile :key="widget.name" :widget="tile" />
</template>
