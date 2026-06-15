<template>
	<Dialog v-model:open="isOpen" bare size="md" position="top">
		<!-- The whole popover is the drop target — scoped to THIS dialog, since
		     upload is a field-level action (a page-wide drop zone would misroute
		     drops and fight other upload fields). Click-to-pick and drop are two
		     parallel paths into the same queue. -->
		<div
			class="relative p-1.5"
			@dragover.prevent="dragging = true"
			@dragleave="onDragLeave"
			@drop.prevent="onDrop"
		>
			<!-- Staged files — held in a soft tray so "what I've added" reads as a
			     distinct zone from the add-menu below (same row styling otherwise). -->
			<div
				v-if="uploader.items.length && !composing"
				class="mb-1.5 rounded-lg border border-outline-gray-1 bg-surface-gray-2 p-1"
			>
				<!-- mini-header: count + bulk Set-all privacy. Optimize is image-only,
				     so it lives on each image row (below), not here. -->
				<div class="flex items-center justify-between px-2 pb-1 pt-0.5">
					<span class="text-xs font-medium text-ink-gray-5">{{ countLabel }}</span>
					<Dropdown :options="bulkPrivacyOptions">
						<button
							type="button"
							class="flex items-center gap-1 rounded px-1.5 py-0.5 text-xs text-ink-gray-6 hover:bg-surface-gray-3"
						>
							<span :class="[bulkPrivacyIcon, 'size-3']" />
							{{ bulkPrivacyLabel }}
							<span class="lucide-chevron-down size-3" />
						</button>
					</Dropdown>
				</div>

				<div
					v-for="item in uploader.items"
					:key="item.id"
					class="group flex items-center gap-2.5 rounded-md px-2 py-1.5 hover:bg-surface-gray-3"
				>
					<!-- thumbnail / kind icon -->
					<div
						class="flex size-8 flex-shrink-0 items-center justify-center overflow-hidden rounded bg-surface-gray-2"
					>
						<img
							v-if="thumbUrl(item)"
							:src="thumbUrl(item)!"
							:alt="item.name"
							class="size-full object-cover"
						/>
						<span v-else :class="[kindIcon(item), 'size-4 text-ink-gray-5']" />
					</div>

					<div class="min-w-0 flex-1">
						<p class="truncate text-p-sm text-ink-gray-8">{{ item.name }}</p>
						<div class="flex items-center gap-1.5 text-xs text-ink-gray-4">
							<span v-if="item.size != null">{{ formatBytes(item.size) }}</span>
							<span v-else-if="item.source === 'link'">Web link</span>
							<!-- inline progress: single/field uploads surface here, not the tray -->
							<span v-if="item.status === 'uploading'"
								>· {{ progressPercent(item) }}%</span
							>
						</div>
						<ErrorMessage v-if="item.error" :message="item.error" class="mt-0.5" />
					</div>

					<!-- thin progress line while uploading -->
					<div
						v-if="item.status === 'uploading'"
						class="h-1 w-14 overflow-hidden rounded-full bg-surface-gray-3"
					>
						<div
							class="h-full rounded-full bg-surface-gray-7 transition-all"
							:style="{ width: `${progressPercent(item)}%` }"
						/>
					</div>
					<span
						v-else-if="item.status === 'done'"
						class="lucide-check-circle-2 size-4 text-ink-green-6"
						aria-hidden="true"
					/>

					<!-- per-item actions — frappe-ui `Button` icon buttons (size xs =
					     24px) so they share the library's hit-area, focus ring, and
					     ghost/subtle styling. Always visible (not hover-revealed) so
					     the actions are discoverable at a glance. Toggles (optimize,
					     privacy) read "on" as a filled `subtle` variant. -->
					<div v-else class="flex items-center gap-0.5">
						<Button
							v-if="item.status === 'error'"
							size="xs"
							variant="ghost"
							icon="lucide-rotate-cw"
							tooltip="Retry"
							aria-label="Retry"
							@click="uploader.retry(item.id)"
						/>
						<Button
							v-if="canCrop(item)"
							size="xs"
							variant="ghost"
							icon="lucide-crop"
							tooltip="Crop"
							aria-label="Crop"
							@click="openCropper(item)"
						/>
						<!-- Optimize: image-only (the server's optimizer ignores other
						     types), so it shows per image rather than queue-wide. The
						     icon carries the state (like privacy's lock/globe): a plain
						     image when off, `image-down` — "will be compressed/
						     downscaled" — when on, so the action stays a ghost button. -->
						<Button
							v-if="canOptimize(item)"
							size="xs"
							variant="ghost"
							:icon="item.optimize ? 'lucide-sparkles' : 'lucide-image-down'"
							:tooltip="item.optimize ? 'Optimization on' : 'Optimize image'"
							:aria-label="item.optimize ? 'Optimization on' : 'Optimize image'"
							:aria-pressed="item.optimize ?? false"
							@click="uploader.setOptimize(item.id, !item.optimize)"
						/>
						<!-- Privacy stays ghost like the rest: the lock/globe icon already
						     carries the state, so it needs no filled "pressed" treatment
						     (which, since files default to private, made every lock look
						     boxed next to the other actions). -->
						<Button
							size="xs"
							variant="ghost"
							:icon="item.isPrivate ? 'lucide-lock' : 'lucide-globe'"
							:tooltip="item.isPrivate ? 'Private' : 'Public'"
							:aria-label="item.isPrivate ? 'Private' : 'Public'"
							:aria-pressed="item.isPrivate"
							@click="uploader.setPrivate(item.id, !item.isPrivate)"
						/>
						<Button
							size="xs"
							variant="ghost"
							icon="lucide-x"
							tooltip="Remove"
							aria-label="Remove"
							@click="uploader.remove(item.id)"
						/>
					</div>
				</div>
			</div>

			<!-- Validation errors: one row each — ErrorMessage renders a single line. -->
			<div v-if="uploader.errors.value.length" class="flex flex-col gap-1 px-2 pb-1">
				<ErrorMessage
					v-for="(error, index) in uploader.errors.value"
					:key="index"
					:message="error"
				/>
			</div>

			<!-- The add region: inline link input / camera capture / the add-menu.
			     Hidden once the queue is full (single-file fields, max reached). -->
			<template v-if="uploader.canAddMore.value">
				<!-- inline link composer (swaps in over the menu) -->
				<div v-if="linkMode" class="flex items-center gap-1.5 px-1 py-1">
					<Button
						variant="ghost"
						icon="lucide-arrow-left"
						tooltip="Back"
						aria-label="Back"
						@click="closeLink"
					/>
					<TextInput
						v-model="linkUrl"
						class="flex-1"
						type="url"
						placeholder="https://example.com/file.pdf"
						@keydown.enter.prevent="submitLink"
					>
						<template #prefix>
							<span
								class="lucide-link size-3.5 text-ink-gray-5"
								aria-hidden="true"
							/>
						</template>
					</TextInput>
					<Button
						variant="solid"
						label="Add"
						:disabled="!linkUrl.trim()"
						@click="submitLink"
					/>
				</div>

				<!-- camera capture (swaps in over the menu) -->
				<div v-else-if="cameraMode" class="px-1 py-1">
					<Button
						class="mb-1.5"
						variant="ghost"
						icon-left="lucide-arrow-left"
						label="Back"
						@click="cameraMode = false"
					/>
					<CameraSource @files="onCameraFiles" />
				</div>

				<!-- the add-menu — labelled "Add more" only once files are staged, so
				     the label separates the two zones without misleading the empty state -->
				<template v-else>
					<p
						v-if="uploader.items.length"
						class="px-2 pb-1 pt-0.5 text-xs font-medium text-ink-gray-5"
					>
						Add more
					</p>
					<button
						v-for="option in menu"
						:key="option.key"
						type="button"
						class="flex w-full items-center gap-2.5 rounded-md px-2 py-1.5 text-left hover:bg-surface-gray-2"
						@click="onMenu(option.key)"
					>
						<span :class="[option.icon, 'size-4 text-ink-gray-6']" />
						<span class="text-p-sm text-ink-gray-8">{{ option.label }}</span>
					</button>
				</template>
			</template>

			<!-- Footer: one divider-topped bar carrying the drop affordance (left)
			     and the Cancel / Upload actions (right), so the hint and the
			     buttons read as a single footer instead of two stacked strips.
			     Cancel gives an explicit dismiss this bare (title-less) popover
			     otherwise lacks — it matters on partial failure, when the dialog
			     stays open for retries. The dragover overlay still covers the whole
			     panel during a drag. -->
			<div
				v-if="!composing && (uploader.items.length || showDropHint)"
				class="mt-1 flex items-center gap-2 border-t border-outline-gray-1 px-2 pb-1 pt-2"
			>
				<p v-if="showDropHint" class="flex items-center gap-1.5 text-xs text-ink-gray-4">
					<span class="lucide-cloud-upload size-3.5" aria-hidden="true" />
					or drop files to upload
				</p>
				<div v-if="uploader.items.length" class="ml-auto flex items-center gap-2">
					<Button
						variant="ghost"
						label="Cancel"
						:disabled="uploader.isUploading.value"
						@click="onCancel"
					/>
					<Button
						variant="solid"
						:label="uploadLabel"
						:loading="uploader.isUploading.value"
						:disabled="uploader.isUploading.value"
						@click="doCommit"
					/>
				</div>
			</div>

			<!-- drop overlay — only while dragging files over this popover -->
			<div
				v-if="dragging"
				class="absolute inset-1 z-10 flex flex-col items-center justify-center gap-1.5 rounded-lg border-2 border-dashed border-outline-gray-4 bg-surface-gray-1/90 text-ink-gray-7"
			>
				<span class="lucide-cloud-upload size-7" />
				<p class="text-p-sm font-medium">Drop files here</p>
			</div>
		</div>
	</Dialog>

	<!-- Hidden native picker driven by the "Upload from device" menu row. -->
	<input
		ref="fileInput"
		type="file"
		class="hidden"
		:multiple="multiple"
		:accept="accept"
		@change="onDeviceInput"
	/>

	<!-- Crop dialog (cropper lazily loaded) — opens over the popover. -->
	<Dialog v-model:open="cropOpen" title="Crop image" size="4xl">
		<ImageCropper
			v-if="cropOpen && cropTarget?.file"
			:file="cropTarget.file"
			:aspectRatio="restrictions?.crop_image_aspect_ratio ?? null"
			@cropped="onCropped"
			@cancel="cropOpen = false"
		/>
	</Dialog>
</template>

<script setup lang="ts">
// The upload dialog, rewritten as a Notion-style add-menu (a quiet `bare`
// popover) instead of the old source tabs. Top-to-bottom: a staged-files tray
// (per-item crop / privacy / remove / retry, with bulk Optimize + Set-all
// privacy), the add-menu (device / link / camera), and a footer (keyboard hint +
// Upload). It owns a `useUploader` instance, bridges each add path into it, and
// on Upload runs `commit()` and emits `committed` with the results.
//
// Progress is a RELAY, never simultaneous (see effectiveProgressMode): multi-file
// hands the queue to the floating `UploadTray` on commit and closes; single/field
// uploads surface inline on the staged rows. The uploader's reactive items
// outlive this component, so a tray upload survives the popover closing.
//
// Public contract is unchanged from the tabbed version (props/emits/doCommit
// semantics) — AttachField, AttachmentsList, and the story consume it as before.
import { computed, defineAsyncComponent, onBeforeUnmount, ref, watch } from "vue";
import { Button, Dialog, Dropdown, ErrorMessage, TextInput } from "frappe-ui";
import CameraSource from "./sources/CameraSource.vue";
import { getUploadSources } from "./sources";
import { useUploader, formatBytes } from "./useUploader";
import { pushTrayBatch, useTray } from "./uploadTray";
import type {
	ProgressMode,
	Restrictions,
	UploadItem,
	UploadResult,
	UploadTransport,
} from "./types";

// Lazy so cropperjs only loads when a crop dialog actually opens.
const ImageCropper = defineAsyncComponent(() => import("./ImageCropper.vue"));

const props = withDefaults(
	defineProps<{
		open: boolean;
		multiple?: boolean;
		imageOnly?: boolean;
		crop?: boolean;
		restrictions?: Restrictions;
		transport?: UploadTransport;
		progressMode?: ProgressMode;
		folder?: string;
		// Accepted for API compatibility with the tabbed dialog; the bare popover
		// has no title bar, so it is not rendered.
		title?: string;
		trayLabel?: string;
	}>(),
	{
		// `progressMode` is intentionally left without a static default so an
		// "unset" mode is distinguishable from an explicit one — see
		// `effectiveProgressMode`.
		multiple: false,
		imageOnly: false,
		crop: false,
		title: "Upload",
		trayLabel: "Uploading files",
	}
);

// How progress is surfaced. When the caller doesn't specify, multi-file uploads
// fall back to the floating tray (so closing the popover mid-upload doesn't lose
// feedback) and single-file to inline. An EXPLICIT mode always wins.
const effectiveProgressMode = computed<ProgressMode>(
	() => props.progressMode ?? (props.multiple ? "tray" : "inline")
);

const emit = defineEmits<{
	"update:open": [boolean];
	committed: [UploadResult[]];
	// Brackets the commit() lifecycle (true while uploading, terminal false).
	// `field` mode uses it to show a spinner while this popover stays open;
	// `tray` mode uses it so a parent that unmounts on close can stay mounted
	// until the not-awaited background commit resolves. `inline` ignores it.
	uploading: [boolean];
}>();

const isOpen = computed({
	get: () => props.open,
	set: (value: boolean) => emit("update:open", value),
});

const uploader = useUploader({
	transport: props.transport,
	restrictions: props.restrictions,
	multiple: props.multiple,
	imageOnly: props.imageOnly,
	folder: props.folder,
});

// ── the add-menu ───────────────────────────────────────────────────────────

// Friendlier, action-phrased labels for the popover (the registry's terse
// "Device"/"Link"/"Camera" read as nouns). Availability (e.g. camera gating)
// still comes from getUploadSources().
const menuMeta: Record<string, { label: string; icon: string }> = {
	device: { label: "Upload from device", icon: "lucide-upload" },
	link: { label: "Embed a link", icon: "lucide-link" },
	camera: { label: "Take a photo", icon: "lucide-camera" },
};
const menu = computed(() =>
	getUploadSources().map((source) => ({
		key: source.key,
		...(menuMeta[source.key] ?? { label: source.label, icon: source.icon }),
	}))
);

const fileInput = ref<HTMLInputElement | null>(null);
const linkMode = ref(false);
const linkUrl = ref("");
const cameraMode = ref(false);

// True while a focused sub-screen (link or camera) is open. These swap in over
// the add-menu with their own back affordance, so the staged tray and the
// Upload/Cancel footer step aside until the user returns — the composer is a
// single-purpose "add one more" view, not a place to act on the queue.
const composing = computed(() => linkMode.value || cameraMode.value);

// The "or drop files" hint belongs to the add-menu state: shown only when the
// queue can still take files and neither composer is open.
const showDropHint = computed(() => uploader.canAddMore.value && !composing.value);

function onMenu(key: string) {
	if (key === "device") fileInput.value?.click();
	else if (key === "link") linkMode.value = true;
	else if (key === "camera") cameraMode.value = true;
}

function onDeviceInput() {
	const el = fileInput.value;
	if (!el?.files) return;
	uploader.add(Array.from(el.files), "device");
	el.value = "";
}

function onCameraFiles(files: File[]) {
	uploader.add(files, "camera");
	cameraMode.value = false;
}

function submitLink() {
	const added = uploader.addLink(linkUrl.value);
	if (added) closeLink();
}

function closeLink() {
	linkUrl.value = "";
	linkMode.value = false;
}

// Native input `accept` filter: images-only fields restrict to images; an
// explicit allowed-types restriction wins over that.
const accept = computed(() => {
	if (props.restrictions?.allowed_file_types?.length) {
		return props.restrictions.allowed_file_types.join(",");
	}
	return props.imageOnly ? "image/*" : undefined;
});

// ── staged rows ──────────────────────────────────────────────────────────────

const countLabel = computed(() => {
	const count = uploader.items.length;
	return `${count} file${count === 1 ? "" : "s"}`;
});

const uploadLabel = computed(() => {
	const count = uploader.items.length;
	return count > 1 ? `Upload ${count} files` : "Upload";
});

// Bulk privacy: the header control reflects the aggregate and flips every file.
const allPrivate = computed(() => uploader.items.every((item) => item.isPrivate));
const allPublic = computed(() => uploader.items.every((item) => !item.isPrivate));
const bulkPrivacyLabel = computed(() =>
	allPrivate.value ? "All private" : allPublic.value ? "All public" : "Mixed"
);
const bulkPrivacyIcon = computed(() => (allPublic.value ? "lucide-globe" : "lucide-lock"));
const bulkPrivacyOptions = [
	{ label: "Make all private", onClick: () => uploader.setAllPrivate(true) },
	{ label: "Make all public", onClick: () => uploader.setAllPrivate(false) },
];

function isImage(item: UploadItem): boolean {
	return Boolean(item.file?.type.startsWith("image/"));
}

function kindIcon(item: UploadItem): string {
	if (item.source === "link") return "lucide-link";
	return isImage(item) ? "lucide-image" : "lucide-file-text";
}

function progressPercent(item: UploadItem): number {
	return Math.round(item.progress * 100);
}

// Crop and optimize are both image-only, row-level actions, offered while the
// item is still idle (before its bytes leave the browser). Crop is no longer
// gated on the field opting in — any staged image can be cropped.
function canCrop(item: UploadItem): boolean {
	return isImage(item) && item.status === "idle";
}

function canOptimize(item: UploadItem): boolean {
	return isImage(item) && item.status === "idle";
}

// Object URLs for image thumbnails. These are minted in a watch — NEVER inside
// the render getter — so rendering stays a pure read. The watch syncs a map to
// the current queue: it creates a URL when an image item appears, re-creates it
// when an item's File is swapped (e.g. after a crop), and revokes it when the
// item leaves the queue (or on unmount).
const thumbnails = ref(new Map<string, { url: string; file: File }>());

function thumbUrl(item: UploadItem): string | null {
	return thumbnails.value.get(item.id)?.url ?? null;
}

watch(
	() => uploader.items.map((item) => [item.id, item.file] as const),
	() => {
		const map = thumbnails.value;
		const present = new Set<string>();
		for (const item of uploader.items) {
			if (!isImage(item) || !item.file) continue;
			present.add(item.id);
			const existing = map.get(item.id);
			if (existing?.file === item.file) continue;
			// New item, or its File was replaced — revoke the stale URL first.
			if (existing) URL.revokeObjectURL(existing.url);
			map.set(item.id, { url: URL.createObjectURL(item.file), file: item.file });
		}
		for (const id of [...map.keys()]) {
			if (present.has(id)) continue;
			URL.revokeObjectURL(map.get(id)!.url);
			map.delete(id);
		}
	},
	{ immediate: true }
);

onBeforeUnmount(() => {
	for (const entry of thumbnails.value.values()) URL.revokeObjectURL(entry.url);
	thumbnails.value.clear();
});

// ── crop ─────────────────────────────────────────────────────────────────────

const cropOpen = ref(false);
const cropTarget = ref<UploadItem | null>(null);

function openCropper(item: UploadItem) {
	cropTarget.value = item;
	cropOpen.value = true;
}

function onCropped(file: File) {
	// replaceFile swaps the item's File; the thumbnail watch sees the new File
	// and re-mints the preview URL (revoking the old one) on its own.
	if (cropTarget.value) uploader.replaceFile(cropTarget.value.id, file);
	cropOpen.value = false;
}

// ── drag & drop (scoped to this popover) ─────────────────────────────────────

const dragging = ref(false);

// Hide the overlay only when the cursor actually leaves the popover, not when it
// crosses between child rows (dragleave fires on every child boundary).
function onDragLeave(event: DragEvent) {
	const target = event.currentTarget as HTMLElement;
	if (!target.contains(event.relatedTarget as Node | null)) dragging.value = false;
}

async function onDrop(event: DragEvent) {
	dragging.value = false;
	const data = event.dataTransfer;
	if (!data) return;

	// Capture both views synchronously — a DataTransfer goes inert once the
	// handler returns, so `webkitGetAsEntry()` and `.files` must be read before
	// any await. Prefer the entries API so dropped folders expand into their
	// files; fall back to the flat FileList when entries aren't available.
	const entries = Array.from(data.items)
		.map((item) => item.webkitGetAsEntry?.())
		.filter(Boolean) as any[];
	const flat = Array.from(data.files);

	if (entries.length) {
		const files: File[] = [];
		for (const entry of entries) await walkEntry(entry, files);
		if (files.length) uploader.add(files, "device");
		return;
	}
	if (flat.length) uploader.add(flat, "device");
}

/** Depth-first walk of a dropped FileSystemEntry tree, collecting files. */
async function walkEntry(entry: any, out: File[]): Promise<void> {
	if (entry.isFile) {
		const file = await new Promise<File>((resolve, reject) => entry.file(resolve, reject));
		out.push(file);
		return;
	}
	if (entry.isDirectory) {
		// readEntries yields entries in batches (Chrome caps at 100 per call), so
		// keep reading until a call returns an empty array to avoid dropping files.
		const reader = entry.createReader();
		while (true) {
			const children: any[] = await new Promise((resolve) =>
				reader.readEntries(resolve, () => resolve([]))
			);
			if (!children.length) break;
			for (const child of children) await walkEntry(child, out);
		}
	}
}

// ── commit ───────────────────────────────────────────────────────────────────

// The tray batch this dialog registered, if any. Kept so repeated commits (e.g.
// retrying a failed row after a partial success) reuse the one batch instead of
// pushing a duplicate — the batch holds a live reference to `uploader.items`, so
// it already reflects retries without re-registering.
let trayBatchId: string | null = null;

// If our tray batch is dismissed (the tray's ✕) while we're lingering mounted
// for retries, release the consumer (`uploading(false)`) so it can unmount us —
// there's nothing left to retry through this instance.
const { batches: trayBatches } = useTray();
watch(
	() => trayBatchId != null && !trayBatches.value.some((b) => b.id === trayBatchId),
	(dismissed) => {
		if (dismissed) emit("uploading", false);
	}
);

// Explicit dismiss: abort any in-flight uploads, drop the queue, and close.
// (`isUploading` disables this in the footer, so we only reach here when idle.)
function onCancel() {
	uploader.cancelAll();
	uploader.clear();
	isOpen.value = false;
}

// Run a tray-mode commit pass and relay its results. Shared by the initial
// Upload click (no `ids` → every pending row) and by the tray's per-item Retry
// (`ids` scoped to that one row), so a retry re-uploads just that file and its
// result reaches the consumer the same way the first pass's did.
//
// `committed` carries only the delta this pass committed, so appending consumers
// never double-count. We release the consumer with `uploading(false)` ONLY once
// the batch has fully settled — while any row is still in `error`, we stay
// "uploading" so a parent like AttachmentsList keeps us mounted and a later tray
// retry can still deliver through us. The `trayBatches` dismiss watch above
// covers the case where the user gives up and closes the tray with failures
// remaining.
function runTrayCommit(ids?: string[]): Promise<void> {
	emit("uploading", true);
	return uploader.commit(ids).then((results) => {
		emit("committed", results);
		if (uploader.items.every((item) => item.status === "done")) {
			emit("uploading", false);
		}
	});
}

async function doCommit() {
	if (!uploader.items.length) return;

	// Tray mode: the floating UploadTray takes over the progress UI, so close the
	// popover the instant Upload is clicked — there's nothing left for it to show.
	// The upload runs to completion in the background (`uploader.items` and the
	// registered tray batch outlive this component). We deliberately do NOT await:
	// closing must not wait for bytes.
	if (effectiveProgressMode.value === "tray") {
		if (trayBatchId == null) {
			trayBatchId = pushTrayBatch(props.trayLabel, uploader.items, {
				cancel: uploader.cancel,
				// Reset the row for immediate feedback, then re-commit just that
				// row; the pass relays the retried result through `committed`.
				retry: (id) => {
					uploader.retry(id);
					void runTrayCommit([id]);
				},
			});
		}
		void runTrayCommit();
		isOpen.value = false;
		return;
	}

	// inline / field: stay open and surface progress on the staged rows. The
	// uploading emit lets a `field`-mode parent spinner while we stay open; the
	// finally guarantees a terminal `false` even if commit() throws.
	emit("uploading", true);
	let results: UploadResult[];
	try {
		results = await uploader.commit();
	} finally {
		emit("uploading", false);
	}
	emit("committed", results);
	// Close on full success; leave open so the user can retry failed rows.
	if (uploader.items.every((item) => item.status === "done")) {
		isOpen.value = false;
	}
}
</script>
