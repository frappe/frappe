<template>
	<div
		class="section"
		:class="[section.hideBorder ? 'pt-4' : 'border-t border-outline-gray-modals mt-5 pt-5']"
	>
		<CollapsibleRoot v-model:open="opened" :disabled="!collapsible">
			<CollapsibleTrigger
				v-if="showHeader"
				as="div"
				class="flex max-w-fit items-center gap-2 text-ink-gray-9"
				:class="{ 'cursor-pointer': collapsible, 'px-3 sm:px-5': hasTabs }"
			>
				<span class="text-base font-medium">{{ section.label }}</span>
				<span
					v-if="collapsible"
					class="lucide-chevron-right size-4"
					:style="{
						transition: 'transform 300ms ease-in-out',
						transform: opened ? 'rotate(90deg)' : 'none',
					}"
					aria-hidden="true"
				/>
			</CollapsibleTrigger>

			<CollapsibleContent
				class="form-section-content"
				:class="{ 'is-animated': animate, animating }"
				force-mount
				@animationend.self="animating = false"
			>
				<div class="flex sm:flex-row flex-col gap-4" :class="{ 'px-3 sm:px-5': hasTabs }">
					<FormLayoutColumn
						v-for="(column, index) in section.columns"
						:key="column.name ?? index"
						:class="{ 'mt-6': showHeader }"
						:column="column"
					/>
				</div>
			</CollapsibleContent>
		</CollapsibleRoot>
	</div>
</template>

<script setup lang="ts">
import { computed, inject, ref, watch } from "vue";
import { CollapsibleContent, CollapsibleRoot, CollapsibleTrigger } from "reka-ui";
import FormLayoutColumn from "./FormLayoutColumn.vue";
import { HasTabsKey } from "./types";
import type { Section } from "./types";

const props = defineProps<{ section: Section }>();

const hasTabs = inject(HasTabsKey);

// Show the header (label + chevron) unless the section opts out.
const showHeader = computed(() => !props.section.hideLabel && !!props.section.label);

// A section can only collapse when it has a header to toggle from.
const collapsible = computed(() => showHeader.value && (props.section.collapsible ?? true));

// Seed open state from the layout; `disabled` keeps non-collapsible sections open.
const opened = ref(props.section.opened ?? true);

// Only animate once the section has actually been toggled — a section that
// renders collapsed should rest at height 0 without playing a collapse
// animation on first paint (reka-ui only skips the mount animation when open).
const animate = ref(false);

// `overflow: hidden` is only needed while the height animation plays. At rest
// we let it return to visible so a focused field's focus ring isn't clipped at
// the section edges. Cleared on `animationend`.
const animating = ref(false);
watch(opened, () => {
	animate.value = true;
	animating.value = true;
});
</script>

<style scoped>
/*
	reka-ui exposes the measured content height as a CSS variable on
	CollapsibleContent, letting us animate height with plain keyframes. Defined
	here (not as Tailwind utilities) so it ships with the component regardless of
	the host app's Tailwind `content` scan.

	We use `force-mount` so the fields stay in the DOM while collapsed — otherwise
	the parent's `.section:not(:has(.field))` rule would hide the whole section
	(header included).

	Animation is gated behind `.is-animated`, which is only added after the first
	toggle. Until then a collapsed section rests at a static `height: 0` with no
	keyframes, so it doesn't flash a collapse animation on first paint.

	Once animating, the collapsed resting state is held by
	`animation-fill-mode: forwards` rather than a static `height: 0`. reka-ui
	re-measures the content height on every open/close by neutralising only the
	animation/transition before reading `getBoundingClientRect()` — a static
	`height: 0` survives that, so the close measurement would read 0 and the
	collapse keyframes would animate 0→0 (i.e. no animation). Letting the keyframes
	own the height keeps the measurement honest.
*/
.form-section-content {
	overflow: hidden;
}
/*
	Only clip while the height animation is in flight. Once the section is open
	and resting, restore `overflow: visible` so a focused field's focus ring can
	paint past the content box instead of being cut off at the section edge.
*/
.form-section-content[data-state="open"]:not(.animating) {
	overflow: visible;
}
.form-section-content:not(.is-animated)[data-state="closed"] {
	height: 0;
}
.form-section-content.is-animated[data-state="open"] {
	animation: form-section-expand 300ms ease-out;
}
.form-section-content.is-animated[data-state="closed"] {
	animation: form-section-collapse 300ms ease-out forwards;
}

@keyframes form-section-expand {
	from {
		height: 0;
	}
	to {
		height: var(--reka-collapsible-content-height);
	}
}
@keyframes form-section-collapse {
	from {
		height: var(--reka-collapsible-content-height);
	}
	to {
		height: 0;
	}
}
</style>
