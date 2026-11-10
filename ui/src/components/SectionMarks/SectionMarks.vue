<!-- A column of marks centred beside a scroll area, one per section. The marks near the pointer
     grow towards it and the sections in view draw brighter; the hovered mark's card shows its
     section's title and description, and a click scrolls to it. It fills its positioned parent's
     height and draws nothing while the area does not scroll. -->
<template>
	<nav
		v-if="tracker?.scrolls.value && sections.length > 1"
		:aria-label="translate('Sections')"
		class="pointer-events-none absolute inset-y-0 z-10 w-6 select-none"
	>
		<div
			class="pointer-events-auto absolute left-0 top-1/2 -translate-y-1/2"
			:style="{ height: stripHeight, width: hovered === null ? '1.5rem' : '22rem' }"
		>
			<button
				type="button"
				class="absolute inset-0 cursor-pointer focus-visible:outline-none"
				:aria-label="translate('Jump to section: {0}', [(preview ?? sections[0]).label])"
				@mousemove="hovered = indexAt($event)"
				@mouseleave="hovered = null"
				@mousedown="onPress"
				@click="onClick"
				@wheel.passive="tracker.viewport.scrollBy({ top: $event.deltaY })"
				@focus="hovered ??= firstInView()"
				@blur="hovered = null"
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
				<span
					v-if="preview"
					data-section-preview
					class="absolute left-8 w-80 cursor-text select-text"
					:style="{ top: `${place(hovered!)}%`, transform: `translateY(${previewShift})` }"
					@mousemove.stop
				>
					<span
						class="block rounded-6 bg-surface-elevation-2 p-3 text-left shadow-xl ring-1 ring-black ring-opacity-5"
					>
						<span class="block truncate text-base font-medium text-ink-gray-8">
							{{ preview.label }}
						</span>
						<span
							v-if="preview.description"
							class="mt-1 line-clamp-3 text-base text-ink-gray-5"
						>
							{{ preview.description }}
						</span>
					</span>
				</span>
			</button>
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

/** The gap between two marks, as T3 Code's thread minimap spaces them. */
const GAP = 8;
/** A mark's width by its distance from the hovered one; the rest stay a third. */
const SCALES = ["scale-x-100", "scale-x-[0.667]", "scale-x-[0.417]"];

const tracker = shallowRef<SectionTracker>();
const hovered = ref<number | null>(null);

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

function inPreview(event: Event) {
	return (event.target as Element).closest("[data-section-preview]") !== null;
}

/** A press on a mark does not focus it, so its card does not stay open on focus. */
function onPress(event: MouseEvent) {
	if (!inPreview(event)) event.preventDefault();
}

function onClick(event: MouseEvent) {
	if (inPreview(event)) return;
	go(indexAt(event));
	(event.currentTarget as HTMLElement).blur();
}

function onKey(event: KeyboardEvent) {
	const last = props.sections.length - 1;
	const moves: Record<string, () => number> = {
		ArrowDown: () => Math.min(last, (hovered.value ?? -1) + 1),
		ArrowUp: () => Math.max(0, (hovered.value ?? 1) - 1),
		Home: () => 0,
		End: () => last,
	};
	if (moves[event.key]) hovered.value = moves[event.key]();
	else if (event.key === "Enter" || event.key === " ") go(hovered.value ?? 0);
	else return;
	event.preventDefault();
}

function go(index: number) {
	const section = props.sections[index];
	if (section) props.find(section.key)?.scrollIntoView({ block: "start", behavior: "smooth" });
}
</script>
