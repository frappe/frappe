<script setup>
import { computed, defineAsyncComponent, onBeforeUpdate, onUpdated, provide, ref } from "vue";
import { block_rects, block_size, glide, split_sections } from "./grid.js";
import GridTile from "./GridTile.vue";
import TextBlock from "./TextBlock.vue";
import NumberCardTile from "./tiles/NumberCardTile.vue";
import ShortcutTile from "./tiles/ShortcutTile.vue";
import CardTile from "./tiles/CardTile.vue";

const props = defineProps({
	content: { type: Array, required: true },
	widgets: { type: Object, required: true },
	// the editor's canvas: blocks are picked and dragged instead of used
	editing: { type: Boolean, default: false },
	selected: { type: String, default: null },
});

const emit = defineEmits(["select", "move"]);
const __ = window.__;
const dragged = ref(null);

// A drop is stored as "insert before block N", or after the last block of a section.
function drop(target) {
	if (dragged.value && dragged.value !== target.id) emit("move", dragged.value, target);
	dragged.value = null;
}

// A block that changes place or size while editing, even between a heading and the grid, glides
// there from where it was. Going in and out of edit mode glides from the page that holds the grid.
const root = ref(null);
let before = new Map();
let was_editing = props.editing;

onBeforeUpdate(() => {
	before = props.editing && was_editing ? block_rects(root.value) : new Map();
});

onUpdated(() => {
	was_editing = props.editing;
	glide(root.value, before, {
		duration: 250,
		easing: "cubic-bezier(0.2, 0, 0, 1)",
		fade_resized: true,
	});
	before = new Map();
});

// a tile that hides itself for its viewer, like a dismissed onboarding, stays on show to edit
provide(
	"editing",
	computed(() => props.editing)
);

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
	const widget = props.widgets[tile.widgets][block.data[tile.key]];
	return widget ? { component: tile.component, props: { widget } } : null;
}
</script>

<template>
	<div ref="root" class="flex flex-col gap-6">
		<section v-for="(section, index) in sections" :key="index" class="flex flex-col gap-3">
			<div
				v-if="section.heading"
				class="ws-frame relative"
				:data-block="section.heading.id"
				:class="
					editing && [
						'-mx-3 min-h-8 px-3',
						section.heading.type === 'header' ? '-mb-1.5 pb-1.5' : '-my-1.5 py-1.5',
					]
				"
			>
				<TextBlock :block="section.heading" />
				<div
					v-if="editing"
					class="ws-pick"
					:class="{ 'ws-picked': selected === section.heading.id }"
					draggable="true"
					@click="emit('select', section.heading)"
					@dragstart="dragged = section.heading.id"
					@dragover.prevent
					@drop.prevent="drop({ id: section.heading.id })"
				/>
			</div>
			<div v-if="section.tiles.length" class="ws-grid">
				<GridTile
					v-for="{ block, size, tile } in section.tiles"
					:key="block.id"
					:size="size"
				>
					<div
						class="relative"
						:data-block="block.id"
						:class="
							block.type === 'paragraph'
								? ['ws-frame', editing && '-mx-3 -my-1.5 px-3 py-1.5']
								: 'ws-block h-full'
						"
					>
						<component :is="tile.component" v-if="tile" v-bind="tile.props" />
						<div
							v-else-if="editing"
							class="flex h-full min-h-14 items-center rounded-6 border border-dashed border-outline-gray-2 p-4 text-base text-ink-gray-5"
						>
							{{ __(block.type.replace("_", " ")) }}
						</div>
						<div
							v-if="editing"
							class="ws-pick"
							:class="{ 'ws-picked': selected === block.id }"
							draggable="true"
							@click="emit('select', block)"
							@dragstart="dragged = block.id"
							@dragover.prevent
							@drop.prevent="drop({ id: block.id })"
						/>
					</div>
				</GridTile>
			</div>
			<div
				v-if="editing && section.tiles.length"
				class="h-4 rounded-4"
				@dragover.prevent
				@drop.prevent="drop({ after: section.tiles.at(-1).block.id })"
			/>
		</section>
	</div>
</template>

<style scoped>
.ws-pick {
	position: absolute;
	inset: 0;
	cursor: grab;
	border-radius: 12px;
}

.ws-pick:active {
	cursor: grabbing;
}

.ws-frame > .ws-pick {
	border-radius: 10px;
	transition-property: box-shadow;
	transition-duration: 150ms;
	transition-timing-function: ease-out;
}

.ws-frame > .ws-pick:hover {
	box-shadow: 0 0 0 1px var(--outline-gray-2), var(--elevation-sm);
}

.ws-block > :first-child {
	transition-property: box-shadow;
	transition-duration: 150ms;
	transition-timing-function: ease-out;
}

.ws-block:has(> .ws-pick:hover) > :first-child {
	box-shadow: 0 0 0 1px var(--outline-gray-2), var(--elevation-md);
}

.ws-block:has(> .ws-pick.ws-picked) > :first-child {
	box-shadow: 0 0 0 1px var(--outline-gray-4), var(--elevation-lg);
}

.ws-frame > .ws-pick.ws-picked {
	box-shadow: 0 0 0 1px var(--outline-gray-4), var(--elevation-md);
}

.ws-grid {
	display: grid;
	grid-template-columns: repeat(2, minmax(0, 1fr));
	grid-auto-rows: calc((var(--ws-row) + var(--ws-gap)) / 18);
	grid-auto-flow: row dense;
	column-gap: var(--ws-gap);
	margin-bottom: calc(-1 * var(--ws-gap));
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
