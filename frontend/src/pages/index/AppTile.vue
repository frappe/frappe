<!-- One app on the index. Its other doors (`fan`) are cards behind the logo that spread on hover or selection;
  they are links of their own, so they sit beside the tile's anchor, not in it. -->
<template>
	<div
		class="fan group relative h-full"
		:data-fanned="fanned || undefined"
		:data-picked="selectedDoor !== null || undefined"
	>
		<a
			:id="id"
			:href="app.route"
			role="option"
			:aria-selected="selected"
			class="flex h-full flex-col items-center gap-2 rounded-5 p-2 outline-none transition group-hover:bg-surface-gray-2 focus-visible:focus-ring"
			:class="{ 'bg-surface-gray-2': fanned }"
			:data-app="app.app"
			:data-selected="selected || undefined"
		>
			<AppLogo
				:logo="app.logo"
				:title="app.title"
				class="fan-logo relative z-[2] transition group-hover:scale-[1.04]"
				:class="{ 'scale-[1.04]': selected || menuOpen }"
			/>
			<span
				class="line-clamp-2 text-center text-sm leading-snug text-ink-gray-8"
				:title="caption"
				data-tile-caption
			>
				{{ caption }}
			</span>
			<span
				v-if="app.fan.length"
				class="-mt-1 line-clamp-1 text-center text-xs leading-snug text-ink-gray-6 transition-opacity group-hover:opacity-0"
				:class="{ 'opacity-0': fanned }"
				data-tile-subtitle
			>
				{{ app.fan.map((card) => card.title).join(" · ") }}
			</span>
		</a>
		<div
			v-if="app.fan.length"
			class="pointer-events-none absolute left-1/2 top-2 z-[1] size-14 -translate-x-1/2"
			data-fan
		>
			<a
				v-for="(card, index) in app.fan"
				:id="doorIds[index]"
				:key="card.route"
				:href="card.route"
				role="option"
				:aria-selected="selectedDoor === index"
				:aria-label="`${card.title}, ${app.title}`"
				tabindex="-1"
				class="fan-card absolute inset-0 z-[1] rounded-[22%] outline-none focus-visible:focus-ring"
				:class="{ 'fan-card-picked': selectedDoor === index }"
				:style="pose(index)"
				data-fan-card
				:data-selected="selectedDoor === index || undefined"
				@mouseenter="hovered = index"
				@mouseleave="hovered = null"
			>
				<span class="fan-face block size-full rounded-[22%] shadow-lg">
					<AppLogo :logo="card.logo" :title="card.title" />
				</span>
			</a>
		</div>
	</div>
</template>

<script setup lang="ts">
import { computed, ref } from "vue";
import type { IndexApp } from "./apps";
import AppLogo from "@/shell/AppLogo.vue";

const props = defineProps<{
	id: string;
	app: IndexApp;
	selected: boolean;
	/** The fan card the arrow keys picked, by position. */
	selectedDoor: number | null;
	doorIds: string[];
	/** The tile's ⋯ menu is open. */
	menuOpen: boolean;
}>();

const hovered = ref<number | null>(null);

const fanned = computed(() => props.selected || props.selectedDoor !== null || props.menuOpen);
const named = computed(() => hovered.value ?? props.selectedDoor);
const caption = computed(() =>
	named.value === null ? props.app.title : props.app.fan[named.value].title
);

// Odd cards lean left, even ones right; the third and fourth sit a step further out.
function pose(index: number) {
	return { "--side": index % 2 === 0 ? -1 : 1, "--step": index > 1 ? 2 : 1 };
}
</script>

<style scoped>
.fan-card {
	/* Resting cards are only an edge behind the logo; a tap there must open the app. */
	pointer-events: none;
	transform-origin: bottom center;
	transform: translateX(calc(var(--side) * var(--step) * 16px))
		rotate(calc(var(--side) * var(--step) * 10deg)) scale(0.84);
	transition: transform 0.3s cubic-bezier(0.34, 1.36, 0.64, 1);
}
.fan-face {
	transform-origin: bottom center;
	transition: transform 0.25s cubic-bezier(0.2, 0.8, 0.2, 1);
}
.fan:hover .fan-card,
.fan[data-fanned] .fan-card {
	pointer-events: auto;
	transform: translateX(calc(var(--side) * var(--step) * 36px))
		rotate(calc(var(--side) * var(--step) * 16deg)) scale(0.9);
}
.fan-card:hover,
.fan-card-picked {
	z-index: 3;
}
/* The cards' wrapper is a stacking context, so a lifted card needs the wrapper above the logo. */
.fan:has(.fan-card:hover) [data-fan],
.fan[data-picked] [data-fan] {
	z-index: 3;
}
.fan-card:hover .fan-face,
.fan-card-picked .fan-face {
	transform: translateY(-8px) rotate(calc(var(--side) * var(--step) * -12deg)) scale(1.11);
}
.fan:has(.fan-card:hover) .fan-logo,
.fan[data-picked] .fan-logo {
	transform: scale(0.92);
}
@media (prefers-reduced-motion: reduce) {
	.fan-card,
	.fan-face {
		transition: none;
	}
}
</style>
