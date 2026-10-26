<script setup>
import { computed, defineAsyncComponent } from "vue";
import { block_size, split_sections } from "./grid.js";
import GridTile from "./GridTile.vue";
import TextBlock from "./TextBlock.vue";
import NumberCardTile from "./tiles/NumberCardTile.vue";
import ShortcutTile from "./tiles/ShortcutTile.vue";
import CardTile from "./tiles/CardTile.vue";

const props = defineProps({
	content: { type: Array, required: true },
	widgets: { type: Object, required: true },
});

// tiles most workspaces do not have load on first use
const ChartTile = defineAsyncComponent(() => import("./tiles/ChartTile.vue"));
const QuickListTile = defineAsyncComponent(() => import("./tiles/QuickListTile.vue"));
const OnboardingTile = defineAsyncComponent(() => import("./tiles/OnboardingTile.vue"));
const CustomBlockTile = defineAsyncComponent(() => import("./tiles/CustomBlockTile.vue"));

const TILES = {
	number_card: { component: NumberCardTile, widgets: "number_cards", key: "number_card_name" },
	chart: { component: ChartTile, widgets: "charts", key: "chart_name" },
	shortcut: { component: ShortcutTile, widgets: "shortcuts", key: "shortcut_name" },
	card: { component: CardTile, widgets: "cards", key: "card_name" },
	quick_list: { component: QuickListTile, widgets: "quick_lists", key: "quick_list_name" },
	onboarding: { component: OnboardingTile, widgets: "onboardings", key: "onboarding_name" },
	custom_block: {
		component: CustomBlockTile,
		widgets: "custom_blocks",
		key: "custom_block_name",
	},
};

const sections = computed(() =>
	split_sections(props.content).map(({ heading, blocks }) => ({
		heading,
		tiles: blocks.map((block) => ({ block, size: block_size(block), tile: tile_for(block) })),
	}))
);

function tile_for(block) {
	if (block.type === "paragraph") return { component: TextBlock, props: { block } };
	const tile = TILES[block.type];
	if (!tile) return null;
	const name = block.data[tile.key];
	return { component: tile.component, props: { widget: props.widgets[tile.widgets][name] } };
}
</script>

<template>
	<div class="flex flex-col gap-6">
		<section v-for="(section, index) in sections" :key="index" class="flex flex-col gap-3">
			<TextBlock v-if="section.heading" :block="section.heading" />
			<div v-if="section.tiles.length" class="ws-grid">
				<GridTile
					v-for="{ block, size, tile } in section.tiles"
					:key="block.id"
					:size="size"
				>
					<component :is="tile.component" v-if="tile" v-bind="tile.props" />
				</GridTile>
			</div>
		</section>
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
