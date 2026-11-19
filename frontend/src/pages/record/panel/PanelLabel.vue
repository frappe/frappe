<!-- A panel row's label: truncates to one line, marks a required field and explains itself on hover or tap. -->
<template>
	<Popover v-if="tipped && coarse" side="bottom" align="start" :auto-focus="false">
		<template #trigger>
			<span ref="row" class="flex h-7 min-w-0 gap-0.5 text-base leading-7 text-ink-gray-5">
				<span ref="text" class="whitespace-nowrap" :aria-hidden="truncated || undefined">{{
					shown
				}}</span>
				<span v-if="truncated" class="sr-only select-none">{{ field.label }}</span>
				<span
					v-if="field.reqd"
					ref="star"
					class="shrink-0 text-ink-red-4"
					role="img"
					:aria-label="__('Required')"
					>*</span
				>
			</span>
		</template>
		<div class="px-2 py-1 text-xs">
			<PanelLabelTip
				:field="field"
				class="text-ink-gray-8"
				description-class="text-ink-gray-5"
			/>
		</div>
	</Popover>
	<Tooltip v-else :disabled="!tipped" :hover-delay="500">
		<span ref="row" class="flex h-7 min-w-0 gap-0.5 text-base leading-7 text-ink-gray-5">
			<span ref="text" class="whitespace-nowrap" :aria-hidden="truncated || undefined">{{
				shown
			}}</span>
			<span v-if="truncated" class="sr-only select-none">{{ field.label }}</span>
			<span
				v-if="field.reqd"
				ref="star"
				class="shrink-0 text-ink-red-4"
				role="img"
				:aria-label="__('Required')"
				>*</span
			>
		</span>
		<template #content>
			<PanelLabelTip :field="field" description-class="text-ink-gray-4" />
		</template>
	</Tooltip>
</template>

<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from "vue";
import { useMediaQuery, useResizeObserver } from "@vueuse/core";
import { Popover, Tooltip } from "frappe-ui";
import type { FieldNode } from "@framework/ui/FormLayout/types";
import { __ } from "@/i18n";
import PanelLabelTip from "./PanelLabelTip.vue";

const props = defineProps<{
	field: FieldNode;
	/** Shows the tip while the row has keyboard focus. */
	tip?: boolean;
}>();

const coarse = useMediaQuery("(pointer: coarse)");
const row = ref<HTMLElement | null>(null);
const text = ref<HTMLElement | null>(null);
const star = ref<HTMLElement | null>(null);
const shown = ref(props.field.label ?? "");
const truncated = ref(false);
const tipped = computed(() => truncated.value || !!props.field.description);

// CSS `text-overflow` leaves up to a glyph of slack between the ellipsis and the `*`. Cutting the
// text here instead puts the `*` the same gap (the row's `gap-0.5`) after the ellipsis as after a full label.
const ELLIPSIS = "\u2026";
let measurer: OffscreenCanvasRenderingContext2D | null | undefined;

function measure() {
	const label = props.field.label ?? "";
	measurer ??=
		typeof OffscreenCanvas === "undefined" ? null : new OffscreenCanvas(1, 1).getContext("2d");
	if (!row.value || !text.value) return;
	if (!measurer) return show(label);
	// The `font` shorthand reads "" when a font feature is set, so the longhands build it.
	const face = getComputedStyle(text.value);
	measurer.font = `${face.fontStyle} ${face.fontWeight} ${face.fontSize} ${face.fontFamily}`;
	const width = (value: string) => measurer!.measureText(value).width;
	const gap = parseFloat(getComputedStyle(row.value).columnGap) || 0;
	// Half a pixel spare, so a rounding error in the canvas never clips the `*`.
	const room = row.value.clientWidth - (star.value ? width("*") + gap : 0) - 0.5;
	if (room <= 0) return;
	if (width(label) <= room) return show(label);
	// The most whole characters whose width plus the ellipsis fits.
	const chars = [...new Intl.Segmenter().segment(label)].map(({ segment }) => segment);
	const cut = (count: number) => chars.slice(0, count).join("").trimEnd() + ELLIPSIS;
	let low = 0;
	let high = chars.length - 1;
	while (low < high) {
		const mid = Math.ceil((low + high) / 2);
		if (width(cut(mid)) <= room) low = mid;
		else high = mid - 1;
	}
	show(cut(low), true);
}

function show(value: string, cut = false) {
	shown.value = value;
	truncated.value = cut;
}

// A web font that loads late widens the text without resizing the row.
onMounted(() => {
	measure();
	document.fonts?.addEventListener("loadingdone", measure);
});
onBeforeUnmount(() => document.fonts?.removeEventListener("loadingdone", measure));
useResizeObserver(row, measure);
// frappe-ui's Tooltip has no controlled `open`, and its trigger opens on `focus` and closes on `blur`.
// An open Tooltip clears `row` while the trigger lives on, so the blur goes to the node the focus reached.
let trigger: HTMLElement | null = null;
watch(
	() => props.tip,
	(on) => {
		trigger = row.value ?? trigger;
		trigger?.dispatchEvent(new FocusEvent(on ? "focus" : "blur"));
	}
);
watch(
	() => [props.field.label, props.field.reqd],
	() => nextTick(measure)
);
</script>
