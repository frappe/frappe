<template>
	<div class="flex flex-col gap-2">
		<draggable
			:list="uploader.items"
			item-key="id"
			handle="[data-drag-handle]"
			:animation="150"
			:disabled="uploader.isUploading.value"
			class="flex flex-col divide-y divide-outline-gray-1"
		>
			<template #item="{ element: item }">
				<div class="flex items-center gap-3 py-2">
					<span
						v-if="uploader.items.length > 1"
						data-drag-handle
						class="lucide-grip-vertical size-4 shrink-0 text-ink-gray-4"
						:class="
							uploader.isUploading.value
								? 'cursor-not-allowed opacity-40'
								: 'cursor-grab'
						"
						aria-hidden="true"
					/>

					<!-- Thumbnail / file-type icon -->
					<button
						type="button"
						class="grid size-11 shrink-0 place-items-center overflow-hidden rounded border border-outline-gray-1 bg-surface-gray-1"
						:class="thumbUrl(item) ? 'cursor-zoom-in' : 'cursor-default'"
						@click="thumbUrl(item) && (lightbox = thumbUrl(item))"
					>
						<img
							v-if="thumbUrl(item)"
							:src="thumbUrl(item)!"
							:alt="item.name"
							class="size-full object-cover"
						/>
						<span
							v-else
							class="lucide-file size-4 text-ink-gray-5"
							aria-hidden="true"
						/>
					</button>

					<!-- Name (editable) + size + per-file private -->
					<div class="flex min-w-0 flex-1 flex-col gap-0.5">
						<input
							:value="item.name"
							class="w-full truncate border-none bg-transparent p-0 text-p-sm text-ink-gray-8 focus:outline-none focus:ring-0"
							:disabled="item.status === 'uploading'"
							@change="rename(item, $event)"
						/>
						<div class="flex items-center gap-2 text-p-xs text-ink-gray-5">
							<span v-if="item.size != null">{{ formatBytes(item.size) }}</span>
							<span v-else-if="item.source === 'link'">Web link</span>
							<Checkbox
								:modelValue="item.isPrivate"
								label="Private"
								class="[&_label]:text-p-xs"
								:disabled="item.status === 'uploading'"
								@update:modelValue="(v: boolean) => uploader.setPrivate(item.id, v)"
							/>
						</div>
						<ErrorMessage v-if="item.error" :message="item.error" class="mt-0.5" />
					</div>

					<!-- Progress / status -->
					<div
						v-if="item.status === 'uploading'"
						class="h-1.5 w-20 overflow-hidden rounded-full bg-surface-gray-3"
					>
						<div
							class="h-full rounded-full bg-surface-gray-7 transition-all"
							:style="{ width: `${Math.round(item.progress * 100)}%` }"
						/>
					</div>
					<span
						v-else-if="item.status === 'done'"
						class="lucide-check-circle-2 size-4 text-ink-green-3"
						aria-hidden="true"
					/>

					<!-- Actions -->
					<div class="flex shrink-0 items-center">
						<Button
							v-if="item.status === 'error'"
							variant="ghost"
							icon="lucide-rotate-cw"
							@click="uploader.retry(item.id)"
						/>
						<Button
							v-if="canCrop(item)"
							variant="ghost"
							icon="lucide-crop"
							@click="openCropper(item)"
						/>
						<Button
							v-if="item.status !== 'uploading'"
							variant="ghost"
							icon="lucide-x"
							@click="uploader.remove(item.id)"
						/>
					</div>
				</div>
			</template>
		</draggable>

		<!-- Lightbox -->
		<Dialog v-model:open="lightboxOpen" size="3xl">
			<img v-if="lightbox" :src="lightbox" alt="" class="mx-auto max-h-[70vh]" />
		</Dialog>

		<!-- Crop dialog (cropper lazily loaded) -->
		<Dialog v-model:open="cropOpen" title="Crop image" size="4xl">
			<ImageCropper
				v-if="cropOpen && cropTarget?.file"
				:file="cropTarget.file"
				:aspectRatio="cropAspectRatio"
				@cropped="onCropped"
				@cancel="cropOpen = false"
			/>
		</Dialog>
	</div>
</template>

<script setup lang="ts">
// Thumbnail gallery view of the uploader queue: per-file thumbnail + lightbox,
// inline rename, size, per-file private toggle, progress bar, remove, retry,
// and reorder via vuedraggable (drag handle). Image items (when crop is on) get
// a crop action that opens the lazily-loaded ImageCropper in a nested dialog and
// swaps the cropped file back into the queue via `replaceFile`.
import { computed, defineAsyncComponent, onBeforeUnmount, ref, watch } from "vue";
import { Button, Checkbox, Dialog, ErrorMessage } from "frappe-ui";
import draggable from "vuedraggable";
import { formatBytes } from "./useUploader";
import type { Uploader } from "./useUploader";
import type { UploadItem } from "./types";

// Lazy so cropperjs only loads when a crop dialog actually opens.
const ImageCropper = defineAsyncComponent(() => import("./ImageCropper.vue"));

const props = defineProps<{
	uploader: Uploader;
	imageOnly?: boolean;
	crop?: boolean;
	/** Fixed crop aspect ratio (from restrictions); free when null. */
	cropAspectRatio?: number | null;
}>();

const lightbox = ref<string | null>(null);
const lightboxOpen = computed({
	get: () => lightbox.value != null,
	set: (open: boolean) => {
		if (!open) lightbox.value = null;
	},
});

const cropOpen = ref(false);
const cropTarget = ref<UploadItem | null>(null);

// Object URLs for image previews, cached per item id and revoked on unmount.
const urls = new Map<string, string>();

function thumbUrl(item: UploadItem): string | null {
	if (item.source === "link") return null;
	if (!item.file || !item.file.type.startsWith("image/")) return null;
	let url = urls.get(item.id);
	if (!url) {
		url = URL.createObjectURL(item.file);
		urls.set(item.id, url);
	}
	return url;
}

function canCrop(item: UploadItem): boolean {
	return (
		Boolean(props.crop || props.imageOnly) &&
		item.status !== "uploading" &&
		item.status !== "done" &&
		Boolean(item.file?.type.startsWith("image/"))
	);
}

function openCropper(item: UploadItem) {
	cropTarget.value = item;
	cropOpen.value = true;
}

function onCropped(file: File) {
	if (cropTarget.value) {
		// Drop the stale preview URL so the new crop renders.
		const old = urls.get(cropTarget.value.id);
		if (old) {
			URL.revokeObjectURL(old);
			urls.delete(cropTarget.value.id);
		}
		props.uploader.replaceFile(cropTarget.value.id, file);
	}
	cropOpen.value = false;
}

function rename(item: UploadItem, event: Event) {
	const value = (event.target as HTMLInputElement).value.trim();
	if (value) item.name = value;
}

// Revoke cached object URLs for items removed from the queue (one-by-one), so
// they don't leak until the whole component unmounts.
watch(
	() => props.uploader.items.map((i) => i.id),
	(ids) => {
		const present = new Set(ids);
		for (const id of urls.keys()) {
			if (present.has(id)) continue;
			URL.revokeObjectURL(urls.get(id)!);
			urls.delete(id);
		}
	}
);

onBeforeUnmount(() => {
	for (const url of urls.values()) URL.revokeObjectURL(url);
	urls.clear();
});
</script>
