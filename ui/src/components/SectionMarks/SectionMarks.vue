<!-- Marks centred beside a scroll area, one per section; a hovered mark shows its section's card
     and a click scrolls to it. It fills its positioned parent's height. -->
<template>
	<nav
		v-if="tracker?.scrolls.value && sections.length > 1"
		:aria-label="translate('Sections')"
		class="pointer-events-none absolute inset-y-0 z-10 w-6 select-none"
	>
		<div
			class="pointer-events-auto absolute left-0 top-1/2 w-6 -translate-y-1/2"
			:style="{ height: stripHeight }"
			@mouseleave="focused || (hovered = null)"
		>
			<button
				type="button"
				class="absolute inset-0 cursor-pointer rounded-2 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-outline-gray-3"
				:aria-label="
					preview
						? translate('Jump to section: {0}', [preview.label])
						: translate('Jump to a section')
				"
				@mousemove="hovered = indexAt($event)"
				@mousedown.prevent
				@click="onClick"
				@wheel.passive="onWheel"
				@focus="onFocus"
				@blur="onBlur"
				@keydown="onKey"
			>
				<span
					v-for="(section, index) in sections"
					:key="section.key"
					aria-hidden="true"
					class="absolute left-0 h-0.5 w-6 origin-left -translate-y-1/2 rounded-full transition-transform duration-150"
					:class="[
						hovered === index ? 'bg-surface-gray-6' : 'bg-surface-gray-4',
						scaleOf(index),
					]"
					:style="{ top: `${place(index)}%` }"
				>
					<span
						class="absolute inset-0 rounded-full bg-surface-gray-7 transition-opacity duration-150"
						:class="
							tracker.inView.value.has(section.key) ? 'opacity-100' : 'opacity-0'
						"
					/>
				</span>
			</button>
			<!-- Not HoverCard: one card follows the pointer along the strip, with no open delay. Its
			     left padding bridges the gap from the marks, so the pointer can reach it. -->
			<div
				v-if="preview"
				class="absolute left-6 w-[21.5rem] cursor-text select-text pl-2"
				:style="{ top: `${place(hovered!)}%`, transform: `translateY(${previewShift})` }"
			>
				<div
					class="rounded-6 bg-surface-elevation-2 p-3 shadow-xl ring-1 ring-black ring-opacity-5"
				>
					<p class="truncate text-base font-medium text-ink-gray-8">
						{{ preview.label }}
					</p>
					<p
						v-if="preview.description"
						class="mt-1 line-clamp-3 text-base text-ink-gray-5"
					>
						{{ preview.description }}
					</p>
				</div>
			</div>
		</div>
	</nav>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, ref, shallowRef, watch } from "vue";
import { translate } from "../../utils/translate";
import { SectionTracker, type MarkedSection } from "./sectionTracker";

const props = defineProps<{
	/** The element that scrolls; unset until the host has mounted it. */
	viewport: HTMLElement | null | undefined;
	sections: MarkedSection[];
	/** A section's element inside the viewport. */
	find: (key: string) => HTMLElement | null;
}>();

const GAP = 8;
/** A mark's width by its distance from the hovered one; the rest stay a third. */
const SCALES = ["scale-x-100", "scale-x-[0.667]", "scale-x-[0.417]"];

const tracker = shallowRef<SectionTracker>();
const hovered = ref<number | null>(null);
const focused = ref(false);

const preview = computed(() => (hovered.value === null ? null : props.sections[hovered.value]));
const stripHeight = computed(
	() => `min(${(props.sections.length - 1) * GAP}px, calc(100% - 4rem))`
);
// The first card hangs down from its mark and the last one up, so neither leaves the strip's ends.
const previewShift = computed(() => {
	if (hovered.value === 0) return "0%";
	return hovered.value === props.sections.length - 1 ? "-100%" : "-50%";
});

watch(
	() => props.viewport,
	(viewport) => {
		tracker.value?.stop();
		tracker.value = viewport
			? new SectionTracker(viewport, () => props.sections, props.find)
			: undefined;
	},
	{ immediate: true }
);
watch(
	() => props.sections,
	() => tracker.value?.measure()
);
onBeforeUnmount(() => tracker.value?.stop());

function place(index: number) {
	return (index / (props.sections.length - 1)) * 100;
}

function scaleOf(index: number) {
	if (hovered.value === null) return "scale-x-[0.333]";
	return SCALES[Math.abs(index - hovered.value)] ?? "scale-x-[0.333]";
}

/** The mark nearest the pointer's height on the strip. */
function indexAt(event: MouseEvent) {
	const rect = (event.currentTarget as HTMLElement).getBoundingClientRect();
	const share = Math.min(1, Math.max(0, (event.clientY - rect.top) / rect.height));
	return Math.round(share * (props.sections.length - 1));
}

function firstInView() {
	const index = props.sections.findIndex(({ key }) => tracker.value?.inView.value.has(key));
	return Math.max(0, index);
}

function onFocus() {
	focused.value = true;
	hovered.value ??= firstInView();
}

function onBlur() {
	focused.value = false;
	hovered.value = null;
}

/** A click from the keyboard or a screen reader has no pointer height: it opens the chosen mark. */
function onClick(event: MouseEvent) {
	go(event.detail ? indexAt(event) : hovered.value ?? firstInView());
}

function onWheel(event: WheelEvent) {
	const lines = event.deltaMode === WheelEvent.DOM_DELTA_LINE;
	tracker.value?.viewport.scrollBy({ top: lines ? event.deltaY * 16 : event.deltaY });
}

function onKey(event: KeyboardEvent) {
	const last = props.sections.length - 1;
	const moves: Record<string, () => number | null> = {
		ArrowDown: () => Math.min(last, (hovered.value ?? -1) + 1),
		ArrowUp: () => Math.max(0, (hovered.value ?? 1) - 1),
		Home: () => 0,
		End: () => last,
		Escape: () => null,
	};
	if (!moves[event.key] || (event.key === "Escape" && hovered.value === null)) return;
	hovered.value = moves[event.key]();
	event.preventDefault();
	// Escape closes the card only, not the dialog around it.
	event.stopPropagation();
}

function go(index: number) {
	const section = props.sections[index];
	if (section) props.find(section.key)?.scrollIntoView({ block: "start", behavior: "smooth" });
}
</script>
