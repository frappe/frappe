<template>
	<div>
		<!-- A read-only TextInput is the display surface (label, description,
		     required indicator, size) — consistent with the other fields. The
		     value is never typed. With a value, activating the field PREVIEWS it
		     (opens the original — the browser renders images/PDFs inline, hands
		     over everything else); re-attaching is a deliberate Replace action, so
		     a stray click never discards the current file. With no value,
		     activating opens the uploader. Read-only keeps preview but hides the
		     Replace/Clear affordances. -->
		<!-- A panel row has no edit state: a click anywhere in the box attaches or replaces,
		     the name is the file's. ↗ keeps the right-edge slot in every row; × sits before it and
		     shows on hover and focus, on editable rows only. -->
		<div v-if="panel" class="group flex h-7 w-full min-w-0 items-center">
			<button
				type="button"
				data-slot="control"
				class="flex h-full min-w-0 flex-1 items-center gap-2 ps-2 pe-2 text-start text-base focus:outline-none"
				:class="field.readOnly ? 'cursor-default' : 'cursor-pointer'"
				:disabled="field.readOnly && !modelValue"
				:aria-label="field.label"
				:aria-invalid="error?.length ? true : undefined"
				@click="onPanelClick"
			>
				<span
					v-if="busy"
					class="lucide-loader-2 size-3.5 shrink-0 animate-spin text-ink-gray-5"
					aria-hidden="true"
				/>
				<img
					v-else-if="imageOnly && modelValue"
					:src="modelValue"
					alt=""
					class="size-5 shrink-0 rounded-2 object-cover"
				/>
				<span class="truncate" :class="modelValue ? 'text-ink-gray-8' : 'text-ink-gray-4'">
					{{ basename || field.placeholder }}
				</span>
			</button>
			<span
				v-if="modelValue"
				class="flex shrink-0 items-center gap-1 pe-2"
				:class="
					field.readOnly
						? ''
						: 'opacity-0 focus-within:opacity-100 group-focus-within:opacity-100 group-hover:opacity-100'
				"
			>
				<button
					v-if="!field.readOnly"
					type="button"
					data-slot="clear"
					:aria-label="__('Clear')"
					:title="__('Clear')"
					class="grid size-4 place-items-center rounded-1 text-ink-gray-5 hover:text-ink-gray-7 focus:outline-none focus-visible:ring-2 focus-visible:ring-outline-gray-3"
					@click="clear"
				>
					<span class="lucide-x size-3.5" />
				</button>
				<a
					:href="modelValue"
					target="_blank"
					rel="noopener"
					:aria-label="__('Open file')"
					:title="__('Open file')"
					class="grid size-4 place-items-center rounded-1 text-ink-gray-5 hover:text-ink-gray-7 focus:outline-none focus-visible:ring-2 focus-visible:ring-outline-gray-3"
				>
					<span class="lucide-arrow-up-right size-3.5" />
				</a>
			</span>
		</div>
		<TextInput
			v-else
			:modelValue="basename"
			:label="field.label"
			:description="field.description"
			:placeholder="field.readOnly ? '—' : field.placeholder || placeholder"
			:required="field.reqd"
			:error="error"
			readonly
			class="group"
			:class="canOpen ? '[&_input]:cursor-pointer' : null"
			@click="onActivate"
			@keydown.enter.prevent="onActivate"
		>
			<template v-if="field.description && !error?.length" #description>
				<FieldDescription :html="field.description" />
			</template>
			<template #prefix>
				<!-- While the dialog is committing, the spinner wins over the
				     thumbnail/icon so a Replace mid-upload reads as busy. -->
				<span
					v-if="busy"
					class="lucide-loader-2 size-3.5 shrink-0 animate-spin text-ink-gray-5"
					aria-hidden="true"
				/>
				<!-- For images the thumbnail doubles as a hover-zoom target: hovering
				     floats a larger preview above the field (passive, delayed so a
				     pass-through across fields doesn't flash); the click still
				     previews. reka-ui flips the card below on collision. -->
				<HoverCard
					v-else-if="imageOnly && modelValue"
					side="top"
					align="start"
					:hoverDelay="400"
					:leaveDelay="100"
				>
					<template #trigger>
						<img
							:src="modelValue"
							alt=""
							class="size-4 shrink-0 rounded-4 object-cover"
						/>
					</template>
					<img
						:src="modelValue"
						alt=""
						class="max-h-64 max-w-72 rounded-5 object-contain p-1"
					/>
				</HoverCard>
				<span
					v-else
					class="pointer-events-none size-3.5 shrink-0"
					:class="[
						imageOnly ? 'lucide-image' : 'lucide-paperclip',
						modelValue ? 'text-ink-gray-7' : 'text-ink-gray-5',
					]"
					aria-hidden="true"
				/>
			</template>
			<!-- Action overlay: revealed on hover/focus. Replace is the only path
			     that re-opens the uploader; Clear empties the field. -->
			<template v-if="!field.readOnly && modelValue" #suffix>
				<div
					class="hidden items-center gap-1 group-hover:flex group-focus:flex group-focus-within:flex"
				>
					<button
						type="button"
						aria-label="Replace"
						class="grid size-4 shrink-0 place-items-center rounded-1 text-ink-gray-5 hover:bg-surface-gray-3 hover:text-ink-gray-7 focus:outline-none focus-visible:ring-2 focus-visible:ring-outline-gray-3"
						@click.stop="openDialog"
						@pointerdown.stop
					>
						<span class="lucide-refresh-cw size-3.5" />
					</button>
					<button
						type="button"
						aria-label="Clear"
						data-slot="clear"
						class="grid size-4 shrink-0 place-items-center rounded-1 text-ink-gray-5 hover:bg-surface-gray-3 hover:text-ink-gray-7 focus:outline-none focus-visible:ring-2 focus-visible:ring-outline-gray-3"
						@click.stop="clear"
						@pointerdown.stop
					>
						<span class="lucide-x size-3.5" />
					</button>
				</div>
			</template>
		</TextInput>

		<FileUploadDialog
			v-if="dialogMounted"
			v-model:open="dialogOpen"
			:title="imageOnly ? 'Attach image' : 'Attach file'"
			:multiple="false"
			:imageOnly="imageOnly"
			:crop="imageOnly"
			:transport="transport"
			:restrictions="restrictions"
			progressMode="field"
			@uploading="onUploading"
			@committed="onCommitted"
		/>
	</div>
</template>

<script setup lang="ts">
// `Attach` / `Attach Image` field. Value is a single `file_url` string (never an
// array — Frappe's attach fieldtypes are single-valued); `imageOnly` is derived
// from the fieldtype, enabling a thumbnail prefix + crop in the dialog. Mirrors
// GeolocationField's read-only-TextInput-opens-a-Dialog shape and LinkField's
// commit semantics (emit both `update:modelValue` and `change`). The dialog is
// lazily mounted so the uploader/cropper load only when attaching.
import { computed, defineAsyncComponent, ref, watch } from "vue";
import { HoverCard, TextInput } from "frappe-ui";
import type { FieldComponentEmits, FieldComponentProps } from "./types";
import type { Restrictions, UploadResult, UploadTransport } from "../FileUpload/types";
import FieldDescription from "./FieldDescription.vue";
import { fileName } from "./fileName";
import { translate as __ } from "../../utils/translate";

const FileUploadDialog = defineAsyncComponent(() => import("../FileUpload/FileUploadDialog.vue"));

// `transport` / `restrictions` are optional presentation props, supplied via the
// node's `ui.props` overlay (e.g. a story's fake transport, or an app's
// site-specific endpoint) — they are NOT part of the portable FieldMeta.
const props = defineProps<
	FieldComponentProps & {
		transport?: UploadTransport;
		restrictions?: Restrictions;
	}
>();
const emit = defineEmits<FieldComponentEmits>();

// `dialogMounted` (v-if) and `dialogOpen` (the modal's open state) are kept
// separate so `field` progress mode can hide the modal the moment an upload
// starts — surfacing the field's own spinner — WITHOUT tearing down the dialog
// mid-commit (which would kill the in-flight upload and lose its result). The
// dialog stays mounted through the whole commit; we only unmount once it settles.
const dialogMounted = ref(false);
const dialogOpen = ref(false);
const busy = ref(false);

const imageOnly = computed(() => props.field.fieldtype === "Attach Image");
const placeholder = computed(() => (imageOnly.value ? "Attach an image" : "Attach a file"));

const basename = computed(() => fileName(props.modelValue));

const canOpen = computed(() => Boolean(props.modelValue) || !props.field.readOnly);

// Activating the field (click / Enter): preview an existing value, otherwise
// open the uploader. Re-attaching never happens here — it's the Replace button.
function onActivate() {
	if (props.modelValue) {
		window.open(props.modelValue, "_blank", "noopener");
	} else {
		openDialog();
	}
}

// A panel row replaces on a click; a read-only one has nothing to replace, so it opens the file.
function onPanelClick() {
	if (busy.value) return;
	if (props.field.readOnly) return props.modelValue ? onActivate() : undefined;
	openDialog();
}

function openDialog() {
	if (props.field.readOnly) return;
	dialogMounted.value = true;
	dialogOpen.value = true;
}

// Upload started/finished. On start, hide the modal so the field spinner shows
// (Gmail-style) while keeping the dialog mounted for the running commit.
function onUploading(value: boolean) {
	busy.value = value;
	if (value) dialogOpen.value = false;
}

function onCommitted(results: UploadResult[]) {
	const first = results[0];
	if (first) {
		emit("update:modelValue", first.file_url);
		emit("change", first.file_url);
		// Upload landed — done with the dialog.
		dialogMounted.value = false;
	} else {
		// Nothing committed (cancelled or every row failed): bring the modal back
		// so the user sees the error rows and can retry.
		dialogOpen.value = true;
	}
}

// A real close (Cancel / backdrop / Esc) unmounts the dialog. Ignore the
// programmatic close we trigger while uploading (busy) — that only hides it.
watch(dialogOpen, (open) => {
	if (!open && !busy.value) dialogMounted.value = false;
});

function clear() {
	emit("update:modelValue", null);
	emit("change", null);
}
</script>
