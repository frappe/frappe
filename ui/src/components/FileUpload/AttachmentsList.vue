<template>
	<div class="flex flex-col gap-2">
		<div
			v-if="modelValue.length"
			class="flex flex-col divide-y divide-outline-gray-1 rounded-lg border border-outline-gray-1"
		>
			<a
				v-for="(attachment, index) in modelValue"
				:key="attachment.file_url + index"
				:href="attachment.file_url"
				target="_blank"
				rel="noopener"
				class="group flex items-center gap-3 px-3 py-2 hover:bg-surface-gray-1"
			>
				<span
					class="grid size-9 shrink-0 place-items-center overflow-hidden rounded border border-outline-gray-1 bg-surface-gray-1"
				>
					<img
						v-if="isImage(attachment.file_url)"
						:src="attachment.file_url"
						:alt="attachment.file_name"
						class="size-full object-cover"
					/>
					<span v-else class="lucide-file size-4 text-ink-gray-5" aria-hidden="true" />
				</span>
				<span class="min-w-0 flex-1 truncate text-p-sm text-ink-gray-8">
					{{ attachment.file_name }}
				</span>
				<span
					v-if="attachment.is_private"
					class="lucide-lock size-3.5 shrink-0 text-ink-gray-4"
					aria-hidden="true"
				/>
				<button
					type="button"
					aria-label="Remove"
					class="grid size-5 shrink-0 place-items-center rounded text-ink-gray-5 opacity-0 hover:bg-surface-gray-3 group-hover:opacity-100"
					@click.prevent="remove(index)"
				>
					<span class="lucide-x size-3.5" />
				</button>
			</a>
		</div>
		<div
			v-else
			class="rounded-lg border border-dashed border-outline-gray-2 p-4 text-center text-p-sm text-ink-gray-5"
		>
			No attachments yet.
		</div>

		<div>
			<Button icon-left="lucide-paperclip" label="Attach" @click="openDialog" />
		</div>

		<FileUploadDialog
			v-if="dialogMounted"
			v-model:open="dialogOpen"
			title="Attach files"
			:multiple="true"
			:imageOnly="imageOnly"
			:crop="crop"
			:restrictions="restrictions"
			:transport="transport"
			progressMode="tray"
			@uploading="onUploading"
			@committed="onCommitted"
		/>
	</div>
</template>

<script setup lang="ts">
// Standalone "attachments list + Attach action" — a consumer of the upload
// primitive that keeps an ARRAY of results (the multi case lives here, never as
// a fieldtype). The Attach button opens the dialog in `multiple` mode; committed
// results are appended. Display-only rows link out, show a private lock, and can
// be removed. The dialog is lazily mounted (v-if) so it's fresh each open and
// its heavy parts load on demand.
import { defineAsyncComponent, ref, watch } from "vue";
import { Button } from "frappe-ui";
import type { Restrictions, UploadResult, UploadTransport } from "./types";

const FileUploadDialog = defineAsyncComponent(() => import("./FileUploadDialog.vue"));

const props = defineProps<{
	modelValue: UploadResult[];
	imageOnly?: boolean;
	crop?: boolean;
	restrictions?: Restrictions;
	transport?: UploadTransport;
}>();

const emit = defineEmits<{ "update:modelValue": [UploadResult[]] }>();

// `dialogMounted` (v-if) is kept separate from `dialogOpen` (the modal's open
// state) because tray mode closes the modal the instant Upload is clicked while
// the commit runs in the background. Binding v-if straight to the open state
// would unmount the dialog before its not-awaited `committed` fires and drop the
// results. Instead we stay mounted until the upload settles (`uploading` false),
// mirroring AttachField.
const dialogMounted = ref(false);
const dialogOpen = ref(false);
const busy = ref(false);

function openDialog() {
	dialogMounted.value = true;
	dialogOpen.value = true;
}

function onCommitted(results: UploadResult[]) {
	emit("update:modelValue", [...props.modelValue, ...results]);
}

// The tray-mode commit brackets itself with `uploading`. `true` arrives as the
// modal closes (keep mounted); `false` arrives once the background commit has
// resolved and `committed` has fired — safe to unmount.
function onUploading(value: boolean) {
	busy.value = value;
	// Unmount on settle — but only if the modal is closed. If the user reopened
	// it while the background upload was finishing, leave it mounted; the
	// dialogOpen watch unmounts it when they close it.
	if (!value && !dialogOpen.value) dialogMounted.value = false;
}

// A real close (Cancel / backdrop / Esc) with no upload in flight unmounts the
// dialog. The programmatic close that tray mode triggers on Upload is ignored
// here (busy guards it) — onUploading owns the unmount in that case.
watch(dialogOpen, (open) => {
	if (!open && !busy.value) dialogMounted.value = false;
});

function remove(index: number) {
	const next = props.modelValue.slice();
	next.splice(index, 1);
	emit("update:modelValue", next);
}

function isImage(url: string): boolean {
	return /\.(png|jpe?g|gif|webp|svg|bmp|avif)(\?|#|$)/i.test(url);
}
</script>
