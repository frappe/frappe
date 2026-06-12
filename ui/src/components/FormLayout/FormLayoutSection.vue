<template>
	<div
		class="section"
		:class="[section.hideBorder ? 'pt-4' : 'border-t border-outline-elevation-2 mt-5 pt-5']"
	>
		<CollapsibleRoot v-model:open="opened" :disabled="!collapsible">
			<CollapsibleTrigger
				v-if="showHeader"
				as="div"
				class="flex max-w-fit items-center gap-2 text-ink-gray-9"
				:class="{ 'cursor-pointer': collapsible, 'px-3 sm:px-5': hasTabs }"
			>
				<span class="text-base-medium">{{ section.label }}</span>
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

const showHeader = computed(() => !props.section.hideLabel && !!props.section.label);

// A section can only collapse when it has a header to toggle from.
const collapsible = computed(() => showHeader.value && (props.section.collapsible ?? true));

const opened = ref(props.section.opened ?? true);

// Gate animation until first toggle, so a section rendered collapsed rests at
// height 0 without playing a collapse animation on first paint.
const animate = ref(false);

// `overflow: hidden` only while animating; at rest visible so a focused field's
// focus ring isn't clipped at the section edges. Cleared on `animationend`.
const animating = ref(false);
watch(opened, () => {
	animate.value = true;
	animating.value = true;
});
</script>

<style scoped>
/*
	Plain keyframes off reka-ui's measured `--reka-collapsible-content-height`,
	defined here (not Tailwind) so they ship regardless of the host's `content` scan.

	`force-mount` keeps fields in the DOM while collapsed, else the parent's
	`.section:not(:has(.field))` rule would hide the whole section.

	The closed resting state is held by the keyframe's `animation-fill-mode:
	forwards`, not a static `height: 0`: reka-ui re-measures height by neutralising
	only animation/transition before `getBoundingClientRect()`, so a static 0 would
	survive and make the close measurement read 0 (animating 0→0).
*/
.form-section-content {
	overflow: hidden;
}
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
