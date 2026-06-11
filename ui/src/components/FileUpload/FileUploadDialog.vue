<template>
	<Dialog v-model:open="isOpen" :title="title" size="2xl">
		<div class="flex flex-col gap-4">
			<!-- Source tabs -->
			<div
				role="tablist"
				aria-label="Upload source"
				class="flex items-center gap-1 border-b border-outline-gray-1 pb-2"
				@keydown="onTabKeydown"
			>
				<button
					v-for="source in sources"
					:id="`upload-tab-${source.key}`"
					:key="source.key"
					ref="tabButtons"
					type="button"
					role="tab"
					:aria-selected="activeKey === source.key"
					:aria-controls="`upload-panel-${source.key}`"
					:tabindex="activeKey === source.key ? 0 : -1"
					class="flex items-center gap-1.5 rounded-md px-2.5 py-1.5 text-p-sm transition-colors"
					:class="
						activeKey === source.key
							? 'bg-surface-gray-2 text-ink-gray-8'
							: 'text-ink-gray-6 hover:bg-surface-gray-1'
					"
					@click="activeKey = source.key"
				>
					<span :class="source.icon" class="size-4" aria-hidden="true" />
					{{ source.label }}
				</button>
			</div>

			<!-- Active source -->
			<component
				:is="activeSource.component"
				:id="`upload-panel-${activeKey}`"
				role="tabpanel"
				:aria-labelledby="`upload-tab-${activeKey}`"
				:accept="accept"
				:multiple="multiple"
				@files="onFiles"
				@link="onLink"
			/>

			<!-- Validation errors: one row each — ErrorMessage renders a single line,
			     so a `\n`-joined string would collapse multiple rejections into one. -->
			<div v-if="uploader.errors.value.length" class="flex flex-col gap-1">
				<ErrorMessage
					v-for="(error, index) in uploader.errors.value"
					:key="index"
					:message="error"
				/>
			</div>

			<!-- Queue -->
			<FileQueue
				v-if="uploader.items.length"
				:uploader="uploader"
				:imageOnly="imageOnly"
				:crop="crop"
				:cropAspectRatio="restrictions?.crop_image_aspect_ratio ?? null"
			/>
		</div>

		<template #actions>
			<div class="flex w-full items-center gap-3">
				<Checkbox
					:modelValue="uploader.isPrivateAll.value"
					label="Private"
					@update:modelValue="(v: boolean) => uploader.setAllPrivate(v)"
				/>
				<Checkbox v-model="uploader.optimizeAll.value" label="Optimize images" />
				<div class="ml-auto flex items-center gap-2">
					<Button label="Cancel" @click="isOpen = false" />
					<Button
						variant="solid"
						:label="uploadLabel"
						:loading="uploader.isUploading.value"
						:disabled="!uploader.items.length || uploader.isUploading.value"
						@click="doCommit"
					/>
				</div>
			</div>
		</template>
	</Dialog>
</template>

<script setup lang="ts">
// The upload dialog: source tabs → active source → live queue → footer (global
// private + optimize toggles, Upload). It owns a `useUploader` instance, bridges
// each source's `files`/`link` into it, and on Upload runs `commit()` and emits
// `committed` with the results.
//
// progressMode (see `effectiveProgressMode`): in `tray` mode the queue is
// registered with the floating `UploadTray` before committing, so a user who
// closes the dialog mid-upload still sees progress there (the uploader's reactive
// items outlive this component; only the post-resolve `committed` emit is lost on
// a manual early close — the tray is the feedback then). `tray` is the implicit
// default for multi-file, but an explicit `inline` is honored. Mirrors
// GeolocationField's heavy-control-behind-Dialog shape; mount lazily (v-if) so
// it's fresh per open.
import { computed, ref } from "vue";
import { Button, Checkbox, Dialog, ErrorMessage } from "frappe-ui";
import FileQueue from "./FileQueue.vue";
import { getUploadSources } from "./sources";
import { useUploader } from "./useUploader";
import { pushTrayBatch } from "./uploadTray";
import type { ProgressMode, Restrictions, UploadResult, UploadTransport } from "./types";

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
// fall back to the floating tray (so closing the dialog mid-upload doesn't lose
// feedback) and single-file to inline. An EXPLICIT mode always wins — so
// `multiple` + `progressMode="inline"` stays inline.
const effectiveProgressMode = computed<ProgressMode>(
	() => props.progressMode ?? (props.multiple ? "tray" : "inline")
);

const emit = defineEmits<{
	"update:open": [boolean];
	committed: [UploadResult[]];
	// Brackets the commit() lifecycle (true while uploading, terminal false).
	// Exists primarily for `field` progressMode so the consuming field can show
	// a spinner while this dialog stays open; tray/inline consumers ignore it.
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

const sources = getUploadSources();
const activeKey = ref(sources[0]?.key ?? "device");
const activeSource = computed(
	() => sources.find((source) => source.key === activeKey.value) ?? sources[0]
);

// Roving-tabindex arrow-key navigation for the WAI-ARIA tablist: Left/Right (and
// Home/End) move selection and focus to the corresponding tab.
const tabButtons = ref<HTMLButtonElement[]>([]);

function onTabKeydown(event: KeyboardEvent) {
	const keys = ["ArrowLeft", "ArrowRight", "Home", "End"];
	if (!keys.includes(event.key)) return;
	event.preventDefault();
	const current = sources.findIndex((source) => source.key === activeKey.value);
	const last = sources.length - 1;
	let next = current;
	if (event.key === "ArrowLeft") next = current <= 0 ? last : current - 1;
	else if (event.key === "ArrowRight") next = current >= last ? 0 : current + 1;
	else if (event.key === "Home") next = 0;
	else if (event.key === "End") next = last;
	activeKey.value = sources[next].key;
	tabButtons.value[next]?.focus();
}

// Native input `accept` filter: images-only fields restrict to images; an
// explicit allowed-types restriction wins over that.
const accept = computed(() => {
	if (props.restrictions?.allowed_file_types?.length) {
		return props.restrictions.allowed_file_types.join(",");
	}
	return props.imageOnly ? "image/*" : undefined;
});

const uploadLabel = computed(() => {
	const count = uploader.items.length;
	return count > 1 ? `Upload ${count} files` : "Upload";
});

function onFiles(files: File[]) {
	uploader.add(files, activeKey.value === "camera" ? "camera" : "device");
}

function onLink(url: string) {
	uploader.addLink(url);
}

// The tray batch this dialog registered, if any. Kept so repeated commits (e.g.
// retrying a failed row after a partial success) reuse the one batch instead of
// pushing a duplicate — the batch holds a live reference to `uploader.items`, so
// it already reflects retries without re-registering.
let trayBatchId: string | null = null;

async function doCommit() {
	const usesTray = effectiveProgressMode.value === "tray";
	if (usesTray && trayBatchId == null) {
		trayBatchId = pushTrayBatch(props.trayLabel, uploader.items, {
			cancel: uploader.cancel,
			retry: uploader.retry,
		});
	}
	// Surface uploading state so a `field`-mode parent can spinner while we stay
	// open; the finally guarantees a terminal `false` even if commit() throws.
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
