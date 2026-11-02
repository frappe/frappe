<script setup>
import {
	computed,
	defineAsyncComponent,
	nextTick,
	onBeforeUnmount,
	onBeforeUpdate,
	onUpdated,
	provide,
	ref,
} from "vue";
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
const GLIDE = { duration: 250, easing: "cubic-bezier(0.2, 0, 0, 1)" };

// A held block follows the pointer, and the page reorders under it as it passes other blocks, so
// the drop is where the gap already is. Escape puts it back. A press that moves less than a few
// pixels is a click and picks the block.
const held = ref(null);
let drag = null;

function press(event, block) {
	if (event.button !== 0) return;
	event.preventDefault();
	const ids = props.content.map((b) => b.id);
	const at = ids.indexOf(block.id);
	drag = {
		id: block.id,
		pointer: { x: event.clientX, y: event.clientY },
		start: { x: event.clientX, y: event.clientY },
		next: ids[at + 1],
		prev: ids[at - 1],
		offset: { x: 0, y: 0 },
	};
	window.addEventListener("pointermove", on_pointer_move);
	window.addEventListener("pointerup", drop);
	window.addEventListener("pointercancel", cancel);
	window.addEventListener("keydown", on_key);
}

function on_pointer_move(event) {
	drag.pointer = { x: event.clientX, y: event.clientY };
	if (!held.value) {
		if (Math.hypot(drag.pointer.x - drag.start.x, drag.pointer.y - drag.start.y) < 4) return;
		lift();
	}
	follow();
	retarget();
}

function lift() {
	const el = held_el();
	const rect = el.getBoundingClientRect();
	drag.el = el;
	drag.grab = { x: drag.start.x - rect.left, y: drag.start.y - rect.top };
	drag.scroller = el.closest(".overflow-y-auto") || document.scrollingElement;
	drag.frame = requestAnimationFrame(scroll_edges);
	document.documentElement.style.cursor = "grabbing";
	held.value = drag.id;
}

function held_el() {
	return root.value?.querySelector(`[data-block="${drag.id}"]`);
}

// keeps the block under the pointer where it was grabbed, wherever its slot is now
function follow() {
	const el = held_el();
	if (!el) return;
	if (el !== drag.el) {
		drag.el = el;
		drag.offset = { x: 0, y: 0 };
	}
	const rect = el.getBoundingClientRect();
	drag.offset = {
		x: drag.pointer.x - drag.grab.x - (rect.left - drag.offset.x),
		y: drag.pointer.y - drag.grab.y - (rect.top - drag.offset.y),
	};
	el.style.transform = `translate(${drag.offset.x}px, ${drag.offset.y}px)`;
}

// A block still gliding out of the way is not a target, or it would swap straight back.
function retarget() {
	const hit = root.value
		.getRootNode()
		.elementFromPoint(drag.pointer.x, drag.pointer.y)
		?.closest("[data-block], [data-drop-after]");
	if (!hit || !root.value.contains(hit)) return (drag.target = null);
	const id = hit.dataset.block || hit.dataset.dropAfter;
	if (id === drag.id || id === drag.target) return;
	if (hit.getAnimations().some((a) => a.playState === "running")) return;
	drag.target = id;
	if (hit.dataset.dropAfter) return emit("move", drag.id, { after: id });
	const ids = props.content.map((b) => b.id);
	emit("move", drag.id, ids.indexOf(drag.id) < ids.indexOf(id) ? { after: id } : { id });
}

function scroll_edges() {
	const box = drag.scroller.getBoundingClientRect();
	const top = Math.max(box.top, 0) + 48;
	const bottom = Math.min(box.bottom, window.innerHeight) - 48;
	const y = drag.pointer.y;
	const by = y < top ? y - top : y > bottom ? y - bottom : 0;
	if (by) {
		drag.scroller.scrollBy(0, by / 3);
		follow();
		retarget();
	}
	drag.frame = requestAnimationFrame(scroll_edges);
}

function on_key(event) {
	if (event.key === "Escape") cancel();
}

function cancel() {
	window.removeEventListener("pointermove", on_pointer_move);
	if (held.value) {
		cancelAnimationFrame(drag.frame);
		emit("move", drag.id, drag.next ? { id: drag.next } : { after: drag.prev });
	}
	nextTick(drop);
}

// the block settles from under the pointer into its slot
function drop() {
	window.removeEventListener("pointermove", on_pointer_move);
	window.removeEventListener("pointerup", drop);
	window.removeEventListener("pointercancel", cancel);
	window.removeEventListener("keydown", on_key);
	if (!held.value) return (drag = null);

	cancelAnimationFrame(drag.frame);
	document.documentElement.style.cursor = "";
	const el = held_el();
	if (el) {
		el.style.transform = "";
		if (!matchMedia("(prefers-reduced-motion: reduce)").matches) {
			const from = `translate(${drag.offset.x}px, ${drag.offset.y}px)`;
			el.animate(
				[
					{ transform: from, zIndex: 10 },
					{ transform: "none", zIndex: 10 },
				],
				GLIDE
			);
		}
	}
	held.value = null;
	drag = null;
}

onBeforeUnmount(drop);

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
	glide(root.value, before, { ...GLIDE, fade_resized: true, held: held.value });
	before = new Map();
	if (held.value) follow();
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
	split_sections(props.content).map(({ heading, divider, blocks }) => ({
		heading,
		divider,
		tiles: blocks.map((block) => ({
			block,
			size: block_size(block),
			tile: tile_for(block),
		})),
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
				:class="[
					held === section.heading.id && 'ws-held',
					editing && [
						'-mx-3 min-h-8 px-3',
						section.heading.type === 'header' ? '-mb-1.5 pb-1.5' : '-my-1.5 py-1.5',
					],
				]"
			>
				<TextBlock :block="section.heading" />
				<div
					v-if="editing"
					class="ws-pick"
					:class="{ 'ws-picked': selected === section.heading.id }"
					@click="emit('select', section.heading)"
					@pointerdown="press($event, section.heading)"
				/>
			</div>
			<div v-else-if="section.divider && !editing" class="h-6" aria-hidden="true" />
			<div
				v-else-if="section.divider"
				class="ws-frame relative -mx-3 -my-1.5 flex items-center gap-3 px-3 py-1.5"
				:data-block="section.divider.id"
				:class="held === section.divider.id && 'ws-held'"
			>
				<span class="h-px flex-1 border-t border-dashed border-outline-gray-3" />
				<span class="text-sm text-ink-gray-5">{{ __("Section break") }}</span>
				<span class="h-px flex-1 border-t border-dashed border-outline-gray-3" />
				<div
					class="ws-pick"
					:class="{ 'ws-picked': selected === section.divider.id }"
					@click="emit('select', section.divider)"
					@pointerdown="press($event, section.divider)"
				/>
			</div>
			<div v-if="section.tiles.length" class="ws-grid">
				<GridTile
					v-for="{ block, size, tile } in section.tiles"
					:key="block.id"
					:size="size"
				>
					<div v-if="held === block.id" class="ws-slot" />
					<div
						class="relative"
						:data-block="block.id"
						:class="[
							held === block.id && 'ws-held',
							block.type === 'paragraph'
								? ['ws-frame', editing && '-mx-3 -my-1.5 px-3 py-1.5']
								: 'ws-block h-full',
						]"
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
							@click="emit('select', block)"
							@pointerdown="press($event, block)"
						/>
					</div>
				</GridTile>
			</div>
			<div
				v-if="editing && section.tiles.length"
				class="h-4 rounded-4"
				:data-drop-after="section.tiles.at(-1).block.id"
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
	touch-action: none;
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
	transition-property: box-shadow, transform;
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

.ws-held {
	z-index: 10;
	pointer-events: none;
}

.ws-block.ws-held > :first-child {
	transform: scale(1.02);
	box-shadow: 0 0 0 1px var(--outline-gray-2), var(--elevation-xl);
}

.ws-frame.ws-held {
	border-radius: 10px;
	background-color: var(--surface-base);
	box-shadow: 0 0 0 1px var(--outline-gray-2), var(--elevation-xl);
}

/* where the held block goes when it is let go */
.ws-slot {
	position: absolute;
	inset: 0 0 var(--ws-gap);
	border-radius: 12px;
	background-color: var(--surface-gray-2);
}

@media (prefers-reduced-motion: reduce) {
	.ws-block.ws-held > :first-child {
		transform: none;
	}
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
	.ws-held {
		z-index: 10;
		pointer-events: none;
	}

	.ws-block.ws-held > :first-child {
		transform: scale(1.02);
		box-shadow: 0 0 0 1px var(--outline-gray-2), var(--elevation-xl);
	}

	.ws-frame.ws-held {
		border-radius: 10px;
		background-color: var(--surface-base);
		box-shadow: 0 0 0 1px var(--outline-gray-2), var(--elevation-xl);
	}

	/* where the held block goes when it is let go */
	.ws-slot {
		position: absolute;
		inset: 0 0 var(--ws-gap);
		border-radius: 12px;
		background-color: var(--surface-gray-2);
	}

	@media (prefers-reduced-motion: reduce) {
		.ws-block.ws-held > :first-child {
			transform: none;
		}
	}

	.ws-grid {
		grid-template-columns: repeat(6, minmax(0, 1fr));
	}
}

@media (min-width: 992px) {
	.ws-held {
		z-index: 10;
		pointer-events: none;
	}

	.ws-block.ws-held > :first-child {
		transform: scale(1.02);
		box-shadow: 0 0 0 1px var(--outline-gray-2), var(--elevation-xl);
	}

	.ws-frame.ws-held {
		border-radius: 10px;
		background-color: var(--surface-base);
		box-shadow: 0 0 0 1px var(--outline-gray-2), var(--elevation-xl);
	}

	/* where the held block goes when it is let go */
	.ws-slot {
		position: absolute;
		inset: 0 0 var(--ws-gap);
		border-radius: 12px;
		background-color: var(--surface-gray-2);
	}

	@media (prefers-reduced-motion: reduce) {
		.ws-block.ws-held > :first-child {
			transform: none;
		}
	}

	.ws-grid {
		grid-template-columns: repeat(12, minmax(0, 1fr));
	}
}
</style>
