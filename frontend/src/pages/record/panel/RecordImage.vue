<!-- The record's picture on the `identity` built-in; an upload lands in `page.doc[image_field]`
     and the header's Save carries it. -->
<template>
	<Tooltip :text="field?.reason ?? ''" :disabled="!field?.reason">
		<div class="group relative size-20 shrink-0" data-record-image>
			<!-- The tile clips the picture itself, so it meets the rounded edge on every side. -->
			<div
				class="size-20 overflow-hidden rounded-[10px] bg-surface-gray-1 ring-1 ring-outline-gray-2"
			>
				<img
					v-if="image && !broken"
					:src="image"
					:alt="label"
					class="size-full object-cover"
					@error="broken = true"
				/>
				<div
					v-else
					class="grid size-full select-none place-items-center text-2xl uppercase text-ink-gray-4"
				>
					{{ initials }}
				</div>
			</div>

			<LoadingIndicator
				v-if="uploading"
				class="absolute left-1/2 top-1/2 size-4 -translate-x-1/2 -translate-y-1/2 text-ink-gray-6"
			/>

			<template v-else-if="editable">
				<div
					v-if="image"
					class="absolute inset-0 flex items-center justify-center gap-1 rounded-[10px] bg-black-overlay-400 opacity-0 transition-opacity focus-within:opacity-100 group-hover:opacity-100"
				>
					<button
						type="button"
						class="grid size-6 place-items-center rounded-1 text-white hover:bg-white-overlay-300"
						aria-label="Replace image"
						@click.stop="attach"
					>
						<span class="lucide-camera size-4" aria-hidden="true" />
					</button>
					<button
						type="button"
						class="grid size-6 place-items-center rounded-1 text-white hover:bg-white-overlay-300"
						aria-label="Remove image"
						@click.stop="setImage('')"
					>
						<span class="lucide-trash-2 size-4" aria-hidden="true" />
					</button>
				</div>

				<button
					v-else
					type="button"
					class="absolute inset-x-0 bottom-0 flex h-1/2 items-end justify-center rounded-b-[10px] bg-black-overlay-50 pb-2 opacity-0 transition-opacity focus-visible:opacity-100 group-hover:opacity-100"
					aria-label="Add image"
					@click.stop="attach"
				>
					<span class="lucide-camera size-4 text-ink-gray-6" aria-hidden="true" />
				</button>
			</template>

			<a
				v-else-if="sourceHref"
				:href="sourceHref"
				target="_blank"
				rel="noopener"
				class="absolute inset-0 grid place-items-center rounded-[10px] bg-black-overlay-400 opacity-0 transition-opacity focus-visible:opacity-100 group-hover:opacity-100"
				aria-label="Open the record this image comes from"
			>
				<span class="lucide-external-link size-4 text-white" aria-hidden="true" />
			</a>

			<FileUploadDialog
				v-if="dialogMounted"
				v-model:open="dialogOpen"
				title="Attach image"
				:multiple="false"
				image-only
				crop
				progress-mode="field"
				:transport="transport"
				@uploading="onUploading"
				@committed="onCommitted"
			/>
		</div>
	</Tooltip>
</template>

<script setup lang="ts">
import { computed, defineAsyncComponent, inject, ref, watch } from "vue";
import { LoadingIndicator, Tooltip, useFileUpload } from "frappe-ui";
import { CommitKey, LinkTitlesKey, NO_COMMIT } from "@framework/ui/components/Fields/types";
import type { UploadResult, UploadTransport } from "@framework/ui/components/FileUpload";
import { routeFor } from "@/router/routeFor";
import { PanelContextKey } from "./context";
import { imageFieldOf, initialsOf } from "./imageField";

const FileUploadDialog = defineAsyncComponent(
	() => import("@framework/ui/components/FileUpload/FileUploadDialog.vue")
);

const props = defineProps<{ label: string }>();

const context = inject(PanelContextKey)!;
const commit = inject(CommitKey, NO_COMMIT);
const titles = inject(LinkTitlesKey, null);

const field = computed(() =>
	imageFieldOf(
		context.meta.value,
		context.doc.value,
		(doctype, name) => titles?.value[`${doctype}::${name}`] || name
	)
);

// Attached to the record: a private File is readable by whoever can read what it hangs on,
// where an unattached one is the uploader's alone and every other reader sees a broken tile.
const transport: UploadTransport = (file, args, ctx) =>
	useFileUpload().upload(file, {
		doctype: context.doctype,
		docname: context.docname,
		fieldname: field.value?.fieldname,
		private: args.isPrivate,
		folder: args.folder,
		optimize: args.optimize,
		max_width: args.maxWidth,
		max_height: args.maxHeight,
		signal: ctx.signal,
		onProgress: ({ loaded, total }) => ctx.onProgress(loaded, total),
	});

const editable = computed(
	() => Boolean(field.value?.editable) && Boolean(context.docinfo.value?.permissions?.write)
);

const image = computed(() =>
	field.value ? String(context.doc.value[field.value.fieldname] || "") : ""
);

/** A fetched picture is changed on its own record, which opens in a tab of its own. */
const sourceHref = computed(() => {
	const source = field.value?.source;
	if (!source || field.value?.editable) return "";
	try {
		return context.controller.page.router.resolve(routeFor(source.doctype, source.name)).href;
	} catch {
		// A doctype this app serves no address for has no page to open.
		return "";
	}
});

const initials = computed(() => initialsOf(props.label));

const broken = ref(false);
const dialogMounted = ref(false);
const dialogOpen = ref(false);
const uploading = ref(false);

// An upload lands in the draft like any other edit, through the commit channel so a
// script's `fields.update` handler on the field fires, and saves with it.
function setImage(url: string) {
	if (!field.value || !editable.value) return;
	context.doc.value = { ...context.doc.value, [field.value.fieldname]: url };
	commit.commit(field.value.fieldname, url);
}

function attach() {
	dialogMounted.value = true;
	dialogOpen.value = true;
}

// The tile shows the spinner while bytes move, so the dialog steps out of the way.
function onUploading(value: boolean) {
	uploading.value = value;
	if (value) dialogOpen.value = false;
}

function onCommitted(results: UploadResult[]) {
	const [uploaded] = results;
	if (uploaded) {
		setImage(uploaded.file_url);
		dialogMounted.value = false;
	} else {
		dialogOpen.value = true;
	}
}

// A real close unmounts; the programmatic one taken while uploading only hides.
watch(dialogOpen, (open) => {
	if (!open && !uploading.value) dialogMounted.value = false;
});

watch(image, () => (broken.value = false));
</script>
