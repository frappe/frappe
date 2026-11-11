<template>
	<div class="flex w-52 flex-col gap-3 p-3" data-slot="color-picker">
		<div
			role="slider"
			tabindex="0"
			data-slot="color-area"
			:aria-label="__('Saturation and brightness')"
			aria-valuemin="0"
			aria-valuemax="100"
			:aria-valuenow="Math.round(hsv.s * 100)"
			:aria-valuetext="areaText"
			class="relative h-32 cursor-crosshair touch-none rounded-4 focus:outline-none focus-visible:ring-2 focus-visible:ring-outline-gray-3"
			:style="areaStyle"
			@pointerdown="(e) => drag(e, 0, (x, y) => adjust({ s: x, v: 1 - y }))"
			@keydown="areaKey"
			@keyup="settle"
			@blur="settle"
		>
			<span
				class="pointer-events-none absolute size-3.5 -translate-x-1/2 -translate-y-1/2 rounded-full border-2 border-white shadow"
				:style="{
					left: `${hsv.s * 100}%`,
					top: `${(1 - hsv.v) * 100}%`,
					backgroundColor: hex,
				}"
			/>
		</div>
		<div class="flex items-center gap-2">
			<Button
				v-if="canSample"
				variant="ghost"
				icon="lucide-pipette"
				:aria-label="__('Pick a color from the screen')"
				:title="__('Pick a color from the screen')"
				@click="sample"
			/>
			<div
				role="slider"
				tabindex="0"
				data-slot="hue"
				:aria-label="__('Hue')"
				aria-valuemin="0"
				aria-valuemax="360"
				:aria-valuenow="Math.round(hsv.h)"
				class="relative h-3 flex-1 cursor-pointer touch-none rounded-full focus:outline-none focus-visible:ring-2 focus-visible:ring-outline-gray-3"
				:style="{ backgroundImage: HUE_GRADIENT }"
				@pointerdown="(e) => drag(e, THUMB_RADIUS, (x) => adjust({ h: x * 360 }))"
				@keydown="hueKey"
				@keyup="settle"
				@blur="settle"
			>
				<span
					class="pointer-events-none absolute top-1/2 size-3.5 -translate-x-1/2 -translate-y-1/2 rounded-full border-2 border-white shadow"
					:style="{
						left: `calc(${THUMB_RADIUS}px + (100% - ${2 * THUMB_RADIUS}px) * ${
							hsv.h / 360
						})`,
						backgroundColor: hueHex,
					}"
				/>
			</div>
		</div>
		<div class="grid grid-cols-[repeat(7,1.25rem)] justify-between gap-y-2">
			<button
				v-for="swatch in SWATCHES"
				:key="swatch"
				type="button"
				data-slot="swatch-option"
				:aria-label="swatch"
				:aria-pressed="swatch === selected"
				class="size-5 rounded-full border border-outline-gray-2 focus:outline-none focus-visible:ring-2 focus-visible:ring-outline-gray-3"
				:class="swatch === selected && 'ring-2 ring-outline-gray-4'"
				:style="{ backgroundColor: swatch }"
				@click="emit('pick', swatch)"
			/>
		</div>
	</div>
</template>

<script setup lang="ts">
import { computed, ref, watch } from "vue";
import { Button } from "frappe-ui";
import { SWATCHES, hexToHsv, hsvToHex, normalizeHex, type Hsv } from "./colorHex";
import { translate as __ } from "../../utils/translate";

const props = defineProps<{ modelValue?: string | null }>();
// `pick` chooses a color and closes; `adjust` follows a drag live and `settle` ends it.
const emit = defineEmits<{ pick: [hex: string]; adjust: [hex: string]; settle: [hex: string] }>();

const THUMB_RADIUS = 7;
const HUE_GRADIENT =
	"linear-gradient(to right, #f00, #ff0 17%, #0f0 33%, #0ff 50%, #00f 67%, #f0f 83%, #f00)";

const selected = computed(() => normalizeHex(props.modelValue ?? ""));
const hsv = ref<Hsv>(selected.value ? hexToHsv(selected.value) : { h: 0, s: 1, v: 1 });
const hex = computed(() => hsvToHex(hsv.value));
const hueHex = computed(() => hsvToHex({ h: hsv.value.h, s: 1, v: 1 }));
const canSample = typeof window !== "undefined" && "EyeDropper" in window;

const areaStyle = computed(() => ({
	backgroundColor: hueHex.value,
	backgroundImage:
		"linear-gradient(to top, #000, transparent), linear-gradient(to right, #fff, transparent)",
}));
const areaText = computed(() =>
	__("Saturation {0}%, brightness {1}%", [
		Math.round(hsv.value.s * 100),
		Math.round(hsv.value.v * 100),
	])
);

// A value from outside moves the thumbs; our own echo would round the hue away.
watch(selected, (value) => {
	if (value && value !== hex.value) hsv.value = hexToHsv(value, hsv.value.h);
});

function adjust(change: Partial<Hsv>) {
	hsv.value = { ...hsv.value, ...change };
	emit("adjust", hex.value);
}

function settle() {
	emit("settle", hex.value);
}

// `inset` keeps the pointer on the thumb where the track stops short of its ends.
function drag(event: PointerEvent, inset: number, move: (x: number, y: number) => void) {
	if (event.button !== 0) return;
	event.preventDefault();
	const el = event.currentTarget as HTMLElement;
	el.focus();
	el.setPointerCapture?.(event.pointerId);
	const follow = (e: PointerEvent) => {
		if (e.pointerId !== event.pointerId) return;
		const box = el.getBoundingClientRect();
		move(
			clamp((e.clientX - box.left - inset) / (box.width - 2 * inset)),
			clamp((e.clientY - box.top) / box.height)
		);
	};
	const ends = ["pointerup", "pointercancel", "lostpointercapture"];
	const end = (e: PointerEvent) => {
		if (e.pointerId !== event.pointerId) return;
		el.removeEventListener("pointermove", follow);
		for (const type of ends) el.removeEventListener(type, end as EventListener);
		settle();
	};
	follow(event);
	el.addEventListener("pointermove", follow);
	for (const type of ends) el.addEventListener(type, end as EventListener);
}

function areaKey(e: KeyboardEvent) {
	const step = e.shiftKey ? 0.1 : 0.01;
	const { s, v } = hsv.value;
	const moves: Record<string, Partial<Hsv>> = {
		ArrowLeft: { s: clamp(s - step) },
		ArrowRight: { s: clamp(s + step) },
		ArrowUp: { v: clamp(v + step) },
		ArrowDown: { v: clamp(v - step) },
	};
	if (!moves[e.key]) return;
	e.preventDefault();
	adjust(moves[e.key]);
}

function hueKey(e: KeyboardEvent) {
	const step = e.shiftKey ? 10 : 1;
	const h = hsv.value.h;
	const moves: Record<string, number> = {
		ArrowLeft: h - step,
		ArrowDown: h - step,
		ArrowRight: h + step,
		ArrowUp: h + step,
		Home: 0,
		End: 360,
	};
	if (moves[e.key] === undefined) return;
	e.preventDefault();
	adjust({ h: Math.min(360, Math.max(0, moves[e.key])) });
}

async function sample() {
	try {
		const { sRGBHex } = await new (window as any).EyeDropper().open();
		const picked = normalizeHex(sRGBHex);
		if (!picked) return;
		hsv.value = hexToHsv(picked, hsv.value.h);
		emit("adjust", picked);
		emit("settle", picked);
	} catch {
		// Escape cancels the eyedropper.
	}
}

function clamp(n: number) {
	return Math.min(1, Math.max(0, n));
}
</script>
