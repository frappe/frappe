<script setup>
import { computed, defineAsyncComponent } from "vue";
import { block_size, split_sections } from "./grid.js";
import GridTile from "./GridTile.vue";
import NumberCardTile from "./tiles/NumberCardTile.vue";

const props = defineProps({
	content: { type: Array, required: true },
	widgets: { type: Object, required: true },
});

const ChartTile = defineAsyncComponent(() => import("./tiles/ChartTile.vue"));

const TILES = {
	number_card: { component: NumberCardTile, widgets: "number_cards", key: "number_card_name" },
	chart: { component: ChartTile, widgets: "charts", key: "chart_name" },
};

const sections = computed(() =>
	split_sections(props.content).map((blocks) =>
		blocks.map((block) => ({ block, size: block_size(block), tile: tile_for(block) }))
	)
);

function tile_for(block) {
	const tile = TILES[block.type];
	if (!tile) return null;
	const name = block.data[tile.key];
	return { component: tile.component, widget: props.widgets[tile.widgets][name] };
}
</script>

<template>
	<div class="flex flex-col gap-6">
		<div v-for="(section, index) in sections" :key="index" class="ws-grid">
			<GridTile v-for="{ block, size, tile } in section" :key="block.id" :size="size">
				<component :is="tile.component" v-if="tile" :widget="tile.widget" />
			</GridTile>
		</div>
	</div>
</template>

<style scoped>
.ws-grid {
	display: grid;
	grid-template-columns: repeat(2, minmax(0, 1fr));
	grid-auto-rows: var(--ws-row);
	grid-auto-flow: row dense;
	gap: var(--ws-gap);
	--ws-row: 3.5rem;
	--ws-gap: 1rem;
}

@media (min-width: 576px) {
	.ws-grid {
		grid-template-columns: repeat(6, minmax(0, 1fr));
	}
}

@media (min-width: 992px) {
	.ws-grid {
		grid-template-columns: repeat(12, minmax(0, 1fr));
	}
}
</style>
