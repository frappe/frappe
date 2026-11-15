<script setup>
import { computed } from "vue";
import { useWidget } from "@framework/ui/widget";
import QuickListTile from "../../page/workspace_view/tiles/QuickListTile.vue";

const { widget, config } = useWidget();

const tile = computed(() => {
	const { document_type, filters = [] } = config.value;
	const rows = filters.map((row) => (row.length === 3 ? [document_type, ...row] : row));
	return {
		...config.value,
		label: widget.value.label,
		hide_filter: widget.value.hide_filter,
		quick_list_filter: JSON.stringify(rows),
	};
});
</script>

<template>
	<QuickListTile :key="widget.name" :widget="tile" />
</template>
