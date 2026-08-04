<template>
	<div class="flex flex-col gap-3">
		<div
			v-if="loadError"
			class="flex h-80 items-center justify-center rounded-lg border border-dashed border-outline-gray-2 p-6 text-center text-p-sm text-ink-gray-6"
		>
			{{ loadError }}
		</div>
		<div v-show="!loadError" class="h-[60vh] overflow-hidden rounded-lg bg-surface-gray-10">
			<!-- cropperjs v2 replaces this <img> with a <cropper-canvas> tree. -->
			<img ref="image" :src="objectUrl" alt="" class="block max-w-full" />
		</div>

		<div v-if="!loadError" class="flex flex-wrap items-center gap-2">
			<div class="flex items-center gap-1">
				<Button
					v-for="preset in presets"
					:key="preset.label"
					size="sm"
					:variant="activePreset === preset.label ? 'solid' : 'subtle'"
					:label="preset.label"
					@click="setAspect(preset.label, preset.value)"
				/>
			</div>
			<Button size="sm" variant="subtle" icon="lucide-rotate-ccw" @click="rotate(-90)" />
			<Button size="sm" variant="subtle" icon="lucide-rotate-cw" @click="rotate(90)" />
			<div class="ml-auto flex items-center gap-2">
				<Button variant="subtle" label="Cancel" @click="emit('cancel')" />
				<Button variant="solid" label="Apply" @click="apply" />
			</div>
		</div>
	</div>
</template>

<script setup lang="ts">
// Image cropper backed by cropperjs v2, lazy-imported exactly like
// GeolocationField does for Leaflet — so cropperjs stays out of the static
// registry import graph and is code-split into a chunk loaded only when a crop
// dialog opens.
//
// v2 is a Web-Components rewrite: `new Cropper(img)` replaces the <img> with a
// `<cropper-canvas>` tree (importing the package auto-registers the elements, so
// there is no stylesheet to load). The selection box owns the aspect ratio and
// exports the result via `$toCanvas()`; the image element owns rotation. Apply
// produces a fresh PNG `File`; the queue swaps it in (`replaceFile`). A failed
// lib load surfaces inline as `loadError` instead of throwing.
import { onBeforeUnmount, onMounted, ref } from "vue";
import { Button } from "frappe-ui";

const props = defineProps<{ file: File; aspectRatio?: number | null }>();
const emit = defineEmits<{ cropped: [File]; cancel: [] }>();

const image = ref<HTMLImageElement | null>(null);
const objectUrl = ref<string>("");
const loadError = ref<string | null>(null);
const activePreset = ref<string>("Free");

// NaN aspect ratio = free-form selection in cropperjs v2.
const presets: { label: string; value: number }[] = [
	{ label: "Free", value: NaN },
	{ label: "1:1", value: 1 },
	{ label: "4:3", value: 4 / 3 },
	{ label: "16:9", value: 16 / 9 },
];

let cropper: any = null;
// The <cropper-selection> element — owns aspect ratio + result export in v2.
let selection: any = null;

onMounted(async () => {
	objectUrl.value = URL.createObjectURL(props.file);
	try {
		await initCropper();
	} catch {
		loadError.value = "The image editor failed to load.";
	}
});

onBeforeUnmount(() => {
	cropper?.destroy?.();
	cropper = null;
	selection = null;
	if (objectUrl.value) URL.revokeObjectURL(objectUrl.value);
});

async function initCropper() {
	// Dynamic import keeps cropperjs lazy and out of the static graph; importing
	// the package self-registers the <cropper-*> custom elements.
	const mod: any = await import("cropperjs");
	const Cropper = mod.default ?? mod;
	if (!image.value) return;

	cropper = new Cropper(image.value);

	// Make the generated <cropper-canvas> fill the fixed-height stage.
	const canvasEl = cropper.getCropperCanvas?.();
	if (canvasEl) {
		canvasEl.style.width = "100%";
		canvasEl.style.height = "100%";
	}

	selection = cropper.getCropperSelection?.();
	if (selection && props.aspectRatio) {
		activePreset.value = "—";
		selection.aspectRatio = props.aspectRatio;
		selection.$reset();
	}
}

function setAspect(label: string, value: number) {
	activePreset.value = label;
	if (!selection) return;
	// Set the ratio (NaN = free) and re-initialise the box to honor it.
	selection.aspectRatio = value;
	selection.$reset();
}

function rotate(deg: number) {
	// v2 rotation lives on the <cropper-image>; angle accepts a CSS unit string.
	cropper?.getCropperImage?.()?.$rotate(`${deg}deg`);
}

async function apply() {
	if (!selection) {
		emit("cancel");
		return;
	}
	// $toCanvas resolves with a canvas of just the selected region.
	const canvas: HTMLCanvasElement = await selection.$toCanvas();
	canvas.toBlob((blob) => {
		if (!blob) {
			emit("cancel");
			return;
		}
		emit(
			"cropped",
			new File([blob], renameCropped(props.file.name), {
				type: "image/png",
			})
		);
	}, "image/png");
}

/** Keep the basename, force a `.png` extension (canvas export is PNG). */
function renameCropped(name: string): string {
	const dot = name.lastIndexOf(".");
	const base = dot === -1 ? name : name.slice(0, dot);
	return `${base}.png`;
}
</script>
