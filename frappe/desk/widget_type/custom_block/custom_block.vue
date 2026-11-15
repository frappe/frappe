<script setup>
import { computed } from "vue";
import { useWidget } from "@framework/ui/widget";
import CustomBlockTile from "../../page/workspace_view/tiles/CustomBlockTile.vue";

const { widget, data } = useWidget();

const tile = computed(() => ({ label: widget.value.label, ...data.value }));
</script>

<template>
	<CustomBlockTile :widget="tile" />
</template>
